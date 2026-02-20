from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.tools import BaseTool

from shukketsu.agent.tools import (
    ALL_TOOLS,
    compare_raid_to_top,
    compare_two_raids,
    get_ability_breakdown,
    get_buff_analysis,
    get_consumable_check,
    get_deaths_and_mechanics,
    get_gear_changes,
    get_my_performance,
    get_raid_execution,
    get_regressions,
    get_resource_usage,
    get_top_rankings,
    get_wipe_progression,
    resolve_my_fights,
)


class TestToolDecorators:
    def test_all_tools_are_base_tool(self):
        for tool in ALL_TOOLS:
            assert isinstance(tool, BaseTool), f"{tool.name} is not a BaseTool"

    def test_all_tools_have_docstrings(self):
        for tool in ALL_TOOLS:
            assert tool.description, f"{tool.name} has no description"

    def test_expected_tool_count(self):
        assert len(ALL_TOOLS) == 30

    def test_tool_names(self):
        names = {t.name for t in ALL_TOOLS}
        expected = {
            "get_my_performance", "get_top_rankings", "compare_to_top",
            "get_fight_details", "get_progression", "get_deaths_and_mechanics",
            "search_fights", "get_spec_leaderboard",
            "compare_raid_to_top", "compare_two_raids", "get_raid_execution",
            "get_ability_breakdown", "get_buff_analysis",
            "get_death_analysis", "get_activity_report", "get_cooldown_efficiency",
            "get_consumable_check", "get_overheal_analysis", "get_cancelled_casts",
            "get_wipe_progression", "get_regressions",
            "resolve_my_fights", "get_gear_changes", "get_phase_analysis",
            "get_resource_usage", "get_cooldown_windows", "get_dot_management",
            "get_rotation_score", "get_trinket_performance",
            "get_enchant_gem_check",
        }
        assert names == expected


class TestGetMyPerformance:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                player_name="TestRogue", player_class="Rogue", player_spec="Combat",
                dps=1500.5, parse_percentile=95.0, ilvl_parse_percentile=90.0,
                deaths=0, item_level=141, encounter_name="Gruul",
                kill=True, duration_ms=180000,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "Gruul", "player_name": "TestRogue"}
            )

        assert "TestRogue" in result
        assert "Gruul" in result


class TestGetTopRankings:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                player_name="TopRogue", player_server="Faerlina",
                amount=2000.0, duration_ms=150000, guild_name="Top Guild",
                item_level=146, rank_position=1,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_top_rankings.ainvoke(
                {"encounter_name": "Gruul", "class_name": "Rogue", "spec_name": "Combat"}
            )

        assert "TopRogue" in result


class TestGetResourceUsage:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                player_name="TestWarr", resource_type="rage",
                min_value=0, max_value=100, avg_value=45.2,
                time_at_zero_ms=5000, time_at_zero_pct=2.8,
                samples_json=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_resource_usage.ainvoke(
                {"report_code": "abc123", "fight_id": 1,
                 "player_name": "TestWarr"}
            )

        assert "rage" in result
        assert "TestWarr" in result
        assert "45.2" in result


class TestGetDeathsAndMechanics:
    async def test_returns_players_with_zero_deaths(self):
        """Tool should return players with interrupts/dispels even if deaths=0."""
        mock_rows = [
            MagicMock(
                player_name="Healer", player_class="Priest", player_spec="Holy",
                deaths=0, interrupts=0, dispels=15,
                encounter_name="Gothik", kill=True, duration_ms=180000,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_deaths_and_mechanics.ainvoke(
                {"encounter_name": "Gothik"}
            )

        assert "Healer" in result
        assert "Disp: 15" in result


class TestCompareRaidToTop:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                fight_id=1, encounter_name="Patchwerk",
                duration_ms=180000, player_count=25,
                total_deaths=2, total_interrupts=0, total_dispels=0,
                avg_dps=1500.0,
                world_record_ms=120000, top10_avg_ms=130000, top100_median_ms=150000,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await compare_raid_to_top.ainvoke({"report_code": "abc123"})

        assert "Patchwerk" in result
        assert "abc123" in result
        assert "Gap" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await compare_raid_to_top.ainvoke({"report_code": "missing"})

        assert "no" in result.lower() or "not found" in result.lower()


class TestCompareTwoRaids:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                encounter_name="Patchwerk",
                a_duration_ms=180000, b_duration_ms=165000,
                a_deaths=3, b_deaths=1,
                a_interrupts=5, b_interrupts=8,
                a_dispels=2, b_dispels=4,
                a_avg_dps=1400.0, b_avg_dps=1600.0,
                a_players=25, b_players=25,
                a_comp="Arms Warrior, Combat Rogue",
                b_comp="Fury Warrior, Combat Rogue",
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await compare_two_raids.ainvoke(
                {"report_a": "abc123", "report_b": "def456"}
            )

        assert "Patchwerk" in result
        assert "faster" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await compare_two_raids.ainvoke(
                {"report_a": "abc123", "report_b": "def456"}
            )

        assert "no" in result.lower() or "not found" in result.lower()


class TestGetRaidExecution:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                encounter_name="Patchwerk", fight_id=1,
                duration_ms=180000, player_count=25,
                total_deaths=2, avg_deaths_per_player=0.08,
                total_interrupts=0, total_dispels=0,
                raid_avg_dps=1500.0, raid_total_dps=37500.0,
                avg_parse=75.0, avg_ilvl=142.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_raid_execution.ainvoke({"report_code": "abc123"})

        assert "Patchwerk" in result
        assert "abc123" in result
        assert "Deaths" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_raid_execution.ainvoke({"report_code": "missing"})

        assert "no" in result.lower() or "not found" in result.lower()


class TestToolErrorHandling:
    async def test_db_error_returns_friendly_message(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "Gruul", "player_name": "Test"}
            )

        assert "Error" in result
        assert "connection lost" in result

    async def test_db_error_on_raid_execution(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("timeout")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_raid_execution.ainvoke({"report_code": "abc123"})

        assert "Error" in result
        assert "timeout" in result

    async def test_db_error_on_compare_raid_to_top(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection refused")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await compare_raid_to_top.ainvoke({"report_code": "abc123"})

        assert "Error" in result


class TestGetAbilityBreakdown:
    async def test_returns_damage_and_healing(self):
        mock_rows = [
            MagicMock(
                player_name="TestWarr", metric_type="damage",
                ability_name="Mortal Strike", spell_id=12294,
                total=50000, hit_count=20, crit_count=10,
                crit_pct=50.0, pct_of_total=45.0,
            ),
            MagicMock(
                player_name="TestWarr", metric_type="healing",
                ability_name="Bloodthirst", spell_id=23881,
                total=5000, hit_count=10, crit_count=2,
                crit_pct=20.0, pct_of_total=100.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_ability_breakdown.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestWarr"}
            )

        assert "Mortal Strike" in result
        assert "Damage abilities" in result
        assert "45.0%" in result

    async def test_no_data_shows_helpful_message(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_ability_breakdown.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "table data" in result.lower() or "not have been ingested" in result.lower()

    async def test_error_handling(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("db error")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_ability_breakdown.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Test"}
            )

        assert "Error" in result


class TestGetBuffAnalysis:
    async def test_returns_buffs_and_debuffs(self):
        mock_rows = [
            MagicMock(
                player_name="TestWarr", metric_type="buff",
                ability_name="Battle Shout", spell_id=2048,
                uptime_pct=95.0, stack_count=0,
            ),
            MagicMock(
                player_name="TestWarr", metric_type="debuff",
                ability_name="Sunder Armor", spell_id=7386,
                uptime_pct=85.0, stack_count=5,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_buff_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestWarr"}
            )

        assert "Battle Shout" in result
        assert "Buffs:" in result
        assert "[HIGH]" in result
        assert "Sunder Armor" in result
        assert "Debuffs" in result

    async def test_buff_tier_labels(self):
        mock_rows = [
            MagicMock(
                player_name="Test", metric_type="buff",
                ability_name="HighBuff", spell_id=1, uptime_pct=95.0, stack_count=0,
            ),
            MagicMock(
                player_name="Test", metric_type="buff",
                ability_name="MedBuff", spell_id=2, uptime_pct=60.0, stack_count=0,
            ),
            MagicMock(
                player_name="Test", metric_type="buff",
                ability_name="LowBuff", spell_id=3, uptime_pct=30.0, stack_count=0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_buff_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Test"}
            )

        assert "[HIGH]" in result
        assert "[MED]" in result
        assert "[LOW]" in result

    async def test_no_data_shows_helpful_message(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_buff_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "table data" in result.lower() or "not have been ingested" in result.lower()


class TestGetMyPerformanceBestsOnly:
    """Tests for get_my_performance with bests_only=True (replaces get_personal_bests)."""

    async def test_returns_formatted_string_multiple_encounters(self):
        mock_rows = [
            MagicMock(
                encounter_name="Patchwerk",
                best_dps=3012.5,
                best_parse=95.2,
                best_hps=0.0,
                kill_count=12,
                peak_ilvl=141.2,
            ),
            MagicMock(
                encounter_name="Sapphiron",
                best_dps=2100.3,
                best_parse=82.0,
                best_hps=50.0,
                kill_count=5,
                peak_ilvl=140.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "", "player_name": "Lyro",
                 "bests_only": True}
            )

        assert "Patchwerk" in result
        assert "Sapphiron" in result
        assert "3,012.5" in result
        assert "95.2%" in result
        assert "Kills: 12" in result

    async def test_with_encounter_filter(self):
        mock_rows = [
            MagicMock(
                encounter_name="Patchwerk",
                best_dps=3012.5,
                best_parse=95.2,
                best_hps=0.0,
                kill_count=12,
                peak_ilvl=141.2,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "Patchwerk", "player_name": "Lyro",
                 "bests_only": True}
            )

        assert "Patchwerk" in result
        assert "3,012.5" in result
        # Verify the encounter_name param was passed to the query
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert "encounter_name" in params

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "", "player_name": "Nobody",
                 "bests_only": True}
            )

        assert "no" in result.lower() or "not found" in result.lower()

    async def test_error_handling(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "", "player_name": "Test",
                 "bests_only": True}
            )

        assert "Error" in result
        assert "connection lost" in result

    async def test_null_parse_and_ilvl(self):
        mock_rows = [
            MagicMock(
                encounter_name="Patchwerk",
                best_dps=1500.0,
                best_parse=None,
                best_hps=0.0,
                kill_count=1,
                peak_ilvl=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "", "player_name": "TestPlayer",
                 "bests_only": True}
            )

        assert "Patchwerk" in result
        assert "1,500.0" in result
        assert "N/A" in result


class TestGetWipeProgression:
    async def test_returns_formatted_progression(self):
        """Tool should show attempt-by-attempt progression with wipes and kills."""
        mock_rows = [
            MagicMock(
                fight_id=1, kill=False, fight_percentage=45.2,
                duration_ms=92000, player_count=25,
                avg_dps=1205.3, total_deaths=8, avg_parse=None,
            ),
            MagicMock(
                fight_id=2, kill=False, fight_percentage=22.1,
                duration_ms=125000, player_count=25,
                avg_dps=1450.0, total_deaths=5, avg_parse=None,
            ),
            MagicMock(
                fight_id=3, kill=True, fight_percentage=0.0,
                duration_ms=195000, player_count=25,
                avg_dps=1890.2, total_deaths=2, avg_parse=65.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_wipe_progression.ainvoke(
                {"report_code": "abc123", "encounter_name": "Patchwerk"}
            )

        assert "WIPE at 45.2%" in result
        assert "WIPE at 22.1%" in result
        assert "KILL" in result
        assert "Attempt 1" in result
        assert "Attempt 2" in result
        assert "Attempt 3" in result
        assert "Parse: 65.0%" in result
        assert "abc123" in result

    async def test_no_data_returns_friendly_message(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_wipe_progression.ainvoke(
                {"report_code": "abc123", "encounter_name": "Patchwerk"}
            )

        assert "no" in result.lower() or "not found" in result.lower()

    async def test_error_handling(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_wipe_progression.ainvoke(
                {"report_code": "abc123", "encounter_name": "Patchwerk"}
            )

        assert "Error" in result
        assert "connection lost" in result

    async def test_fight_percentage_appears_for_wipes(self):
        """Verify fight_percentage is shown for wipe attempts."""
        mock_rows = [
            MagicMock(
                fight_id=1, kill=False, fight_percentage=73.5,
                duration_ms=45000, player_count=25,
                avg_dps=800.0, total_deaths=15, avg_parse=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_wipe_progression.ainvoke(
                {"report_code": "xyz789", "encounter_name": "Kel'Thuzad"}
            )

        assert "73.5%" in result
        assert "WIPE" in result


class TestGetRegressions:
    async def test_returns_regression_and_improvement(self):
        """Tool should show both regressions and improvements."""
        mock_rows = [
            MagicMock(
                player_name="Lyro",
                encounter_name="Patchwerk",
                recent_parse=72.0,
                baseline_parse=90.2,
                recent_dps=1205.3,
                baseline_dps=1890.0,
                parse_delta=-18.2,
                dps_delta_pct=-36.2,
            ),
            MagicMock(
                player_name="Lyro",
                encounter_name="Grobbulus",
                recent_parse=88.5,
                baseline_parse=70.1,
                recent_dps=1650.0,
                baseline_dps=1350.0,
                parse_delta=18.4,
                dps_delta_pct=22.2,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_regressions.ainvoke({})

        assert "REGRESSION" in result
        assert "IMPROVEMENT" in result
        assert "Lyro" in result
        assert "Patchwerk" in result
        assert "Grobbulus" in result
        assert "72.0%" in result
        assert "90.2%" in result
        assert "88.5%" in result
        assert "70.1%" in result

    async def test_with_player_filter(self):
        """Tool should filter by player_name when provided."""
        mock_rows = [
            MagicMock(
                player_name="Lyro",
                encounter_name="Patchwerk",
                recent_parse=72.0,
                baseline_parse=90.2,
                recent_dps=1205.3,
                baseline_dps=1890.0,
                parse_delta=-18.2,
                dps_delta_pct=-36.2,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_regressions.ainvoke({"player_name": "Lyro"})

        assert "Lyro" in result
        assert "Patchwerk" in result
        # Verify the player_name param was used
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert "player_name" in params

    async def test_no_regressions_returns_friendly_message(self):
        """Tool should return a friendly message when no regressions found."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_regressions.ainvoke({})

        assert "no significant" in result.lower() or "normal range" in result.lower()

    async def test_error_handling(self):
        """Tool should return error string on DB failure."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_regressions.ainvoke({})

        assert "Error" in result
        assert "connection lost" in result

    async def test_null_dps_delta_pct(self):
        """Tool should handle None dps_delta_pct (when baseline DPS is 0)."""
        mock_rows = [
            MagicMock(
                player_name="Lyro",
                encounter_name="Patchwerk",
                recent_parse=72.0,
                baseline_parse=90.2,
                recent_dps=1205.3,
                baseline_dps=0.0,
                parse_delta=-18.2,
                dps_delta_pct=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_regressions.ainvoke({})

        assert "REGRESSION" in result
        assert "N/A" in result


class TestResolveMyFights:
    async def test_returns_recent_kills(self):
        """Tool should return formatted list of recent kills."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=4, encounter_name="Patchwerk",
                dps=2847.3, parse_percentile=92.1, deaths=0, item_level=141,
                duration_ms=195000, report_title="Naxx Run", report_time=None,
            ),
            MagicMock(
                report_code="abc123", fight_id=7, encounter_name="Patchwerk",
                dps=2691.0, parse_percentile=85.4, deaths=1, item_level=140,
                duration_ms=202000, report_title="Naxx Run", report_time=None,
            ),
            MagicMock(
                report_code="xyz789", fight_id=2, encounter_name="Grobbulus",
                dps=1950.5, parse_percentile=78.0, deaths=0, item_level=139,
                duration_ms=241000, report_title="Naxx Alt Run", report_time=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await resolve_my_fights.ainvoke({})

        assert "abc123" in result
        assert "xyz789" in result
        assert "Patchwerk" in result
        assert "Grobbulus" in result
        assert "2,847.3" in result
        assert "92.1%" in result
        assert "fight #4" in result
        assert "fight #2" in result

    async def test_with_encounter_filter(self):
        """Tool should pass encounter_name filter to query."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=4, encounter_name="Patchwerk",
                dps=2847.3, parse_percentile=92.1, deaths=0, item_level=141,
                duration_ms=195000, report_title="Naxx Run", report_time=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await resolve_my_fights.ainvoke(
                {"encounter_name": "Patchwerk"}
            )

        assert "Patchwerk" in result
        assert "abc123" in result
        # Verify encounter_name was passed to the query
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["encounter_name"] == "%Patchwerk%"

    async def test_no_data(self):
        """Tool should return friendly message when no kills found."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await resolve_my_fights.ainvoke({})

        assert "no recent kills" in result.lower()

    async def test_no_data_with_filter(self):
        """Tool should include encounter name in no-data message."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await resolve_my_fights.ainvoke(
                {"encounter_name": "Sapphiron"}
            )

        assert "no recent kills" in result.lower()
        assert "Sapphiron" in result

    async def test_error_handling(self):
        """Tool should return error string on DB failure."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await resolve_my_fights.ainvoke({})

        assert "Error" in result
        assert "connection lost" in result

    async def test_null_parse_percentile(self):
        """Tool should handle None parse_percentile gracefully."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=1, encounter_name="Patchwerk",
                dps=1500.0, parse_percentile=None, deaths=0, item_level=130,
                duration_ms=200000, report_title="Naxx Run", report_time=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await resolve_my_fights.ainvoke({})

        assert "N/A" in result
        assert "Patchwerk" in result

    async def test_custom_count(self):
        """Tool should pass count parameter to limit."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            await resolve_my_fights.ainvoke({"count": 3})

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 3


class TestGetConsumableCheck:
    async def test_returns_consumables_per_player(self):
        """Tool should show consumables grouped by player with categories."""
        # First call returns fight details (for encounter name header)
        fight_detail_rows = [
            MagicMock(
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=2000.0, hps=0.0, parse_percentile=90.0, deaths=0,
                interrupts=0, dispels=0, item_level=141,
                kill=True, duration_ms=180000,
                encounter_name="Patchwerk", report_title="Naxx Run",
            ),
        ]
        fight_detail_result = MagicMock()
        fight_detail_result.fetchall.return_value = fight_detail_rows

        # Second call returns consumable data for two players
        consumable_rows = [
            MagicMock(
                player_name="Lyro", category="flask",
                ability_name="Flask of Supreme Power", spell_id=17628, active=True,
            ),
            MagicMock(
                player_name="Lyro", category="food",
                ability_name="Well Fed", spell_id=33254, active=True,
            ),
            MagicMock(
                player_name="Lyro", category="weapon_oil",
                ability_name="Brilliant Wizard Oil", spell_id=28898, active=True,
            ),
            MagicMock(
                player_name="Healbot", category="flask",
                ability_name="Flask of Distilled Wisdom", spell_id=17627, active=True,
            ),
            MagicMock(
                player_name="Healbot", category="food",
                ability_name="Well Fed", spell_id=33254, active=True,
            ),
        ]
        consumable_result = MagicMock()
        consumable_result.fetchall.return_value = consumable_rows

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [fight_detail_result, consumable_result]

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_consumable_check.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        assert "Patchwerk" in result
        assert "Lyro" in result
        assert "Healbot" in result
        assert "Flask of Supreme Power" in result
        assert "Flask of Distilled Wisdom" in result
        assert "Well Fed" in result
        assert "Brilliant Wizard Oil" in result

    async def test_flags_missing_categories(self):
        """Tool should flag missing flask/elixir, food, and weapon_oil."""
        fight_detail_rows = [
            MagicMock(
                player_name="Healbot", player_class="Priest", player_spec="Holy",
                dps=0.0, hps=1500.0, parse_percentile=80.0, deaths=0,
                interrupts=0, dispels=0, item_level=140,
                kill=True, duration_ms=180000,
                encounter_name="Patchwerk", report_title="Naxx Run",
            ),
        ]
        fight_detail_result = MagicMock()
        fight_detail_result.fetchall.return_value = fight_detail_rows

        # Player only has food, missing flask/elixir and weapon_oil
        consumable_rows = [
            MagicMock(
                player_name="Healbot", category="food",
                ability_name="Well Fed", spell_id=33254, active=True,
            ),
        ]
        consumable_result = MagicMock()
        consumable_result.fetchall.return_value = consumable_rows

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [fight_detail_result, consumable_result]

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_consumable_check.ainvoke(
                {"report_code": "abc123", "fight_id": 4, "player_name": "Healbot"}
            )

        assert "Healbot" in result
        assert "MISSING" in result
        assert "flask/elixir" in result
        assert "weapon_oil" in result

    async def test_elixir_satisfies_flask_requirement(self):
        """Having an elixir should not flag missing flask/elixir."""
        fight_detail_rows = [
            MagicMock(
                player_name="Rogue", player_class="Rogue", player_spec="Combat",
                dps=1800.0, hps=0.0, parse_percentile=85.0, deaths=0,
                interrupts=0, dispels=0, item_level=138,
                kill=True, duration_ms=180000,
                encounter_name="Patchwerk", report_title="Naxx Run",
            ),
        ]
        fight_detail_result = MagicMock()
        fight_detail_result.fetchall.return_value = fight_detail_rows

        consumable_rows = [
            MagicMock(
                player_name="Rogue", category="battle_elixir",
                ability_name="Elixir of the Mongoose", spell_id=17538, active=True,
            ),
            MagicMock(
                player_name="Rogue", category="food",
                ability_name="Well Fed", spell_id=33254, active=True,
            ),
        ]
        consumable_result = MagicMock()
        consumable_result.fetchall.return_value = consumable_rows

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [fight_detail_result, consumable_result]

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_consumable_check.ainvoke(
                {"report_code": "abc123", "fight_id": 4, "player_name": "Rogue"}
            )

        assert "flask/elixir" not in result
        assert "Elixir of the Mongoose" in result

    async def test_no_data_returns_helpful_message(self):
        """Tool should return a message when no consumable data exists."""
        fight_detail_rows = [
            MagicMock(
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=2000.0, hps=0.0, parse_percentile=90.0, deaths=0,
                interrupts=0, dispels=0, item_level=141,
                kill=True, duration_ms=180000,
                encounter_name="Patchwerk", report_title="Naxx Run",
            ),
        ]
        fight_detail_result = MagicMock()
        fight_detail_result.fetchall.return_value = fight_detail_rows

        consumable_result = MagicMock()
        consumable_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [fight_detail_result, consumable_result]

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_consumable_check.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        assert "no consumable data" in result.lower() or "not have been ingested" in result.lower()

    async def test_error_handling(self):
        """Tool should return error string on DB failure."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_consumable_check.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        assert "Error" in result
        assert "connection lost" in result


class TestGetGearChanges:
    async def test_returns_upgrades_and_downgrades(self):
        """Tool should show slot names, old/new items, and ilvl deltas."""
        mock_rows = [
            MagicMock(
                slot=0, old_item_id=30104, old_ilvl=141,
                new_item_id=30120, new_ilvl=146,
            ),
            MagicMock(
                slot=15, old_item_id=30311, old_ilvl=141,
                new_item_id=28297, new_ilvl=128,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_gear_changes.ainvoke(
                {"player_name": "Lyro", "report_code_old": "abc123",
                 "report_code_new": "xyz789"}
            )

        assert "Lyro" in result
        assert "abc123" in result
        assert "xyz789" in result
        assert "Head" in result
        assert "Main Hand" in result
        assert "+5 ilvl" in result
        assert "-13 ilvl" in result

    async def test_no_changes_returns_friendly_message(self):
        """Tool should return friendly message when no gear changes found."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_gear_changes.ainvoke(
                {"player_name": "Lyro", "report_code_old": "abc123",
                 "report_code_new": "xyz789"}
            )

        assert "no gear changes" in result.lower()
        assert "Lyro" in result

    async def test_new_slot_shows_empty_old(self):
        """Tool should handle slots where only the new gear exists."""
        mock_rows = [
            MagicMock(
                slot=13, old_item_id=None, old_ilvl=None,
                new_item_id=30627, new_ilvl=141,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_gear_changes.ainvoke(
                {"player_name": "Lyro", "report_code_old": "abc123",
                 "report_code_new": "xyz789"}
            )

        assert "Trinket 2" in result
        assert "empty" in result
        assert "30627" in result

    async def test_error_handling(self):
        """Tool should return error string on DB failure."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_gear_changes.ainvoke(
                {"player_name": "Lyro", "report_code_old": "abc123",
                 "report_code_new": "xyz789"}
            )

        assert "Error" in result
        assert "connection lost" in result


class TestNoResults:
    async def test_get_my_performance_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "Gruul", "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not found" in result.lower()
