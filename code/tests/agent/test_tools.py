from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.tools import BaseTool

from shukketsu.agent.tools import (
    ALL_TOOLS,
    compare_raid_to_top,
    compare_two_raids,
    get_ability_breakdown,
    get_buff_analysis,
    get_cooldown_windows,
    get_deaths_and_mechanics,
    get_dot_analysis,
    get_gear_audit,
    get_my_performance,
    get_phase_breakdown,
    get_raid_buff_coverage,
    get_raid_execution,
    get_raid_summary,
    get_resource_usage,
    get_rotation_score,
    get_threat_analysis,
    get_top_rankings,
    get_trinket_procs,
)


class TestToolDecorators:
    def test_all_tools_are_base_tool(self):
        for tool in ALL_TOOLS:
            assert isinstance(tool, BaseTool), f"{tool.name} is not a BaseTool"

    def test_all_tools_have_docstrings(self):
        for tool in ALL_TOOLS:
            assert tool.description, f"{tool.name} has no description"

    def test_expected_tool_count(self):
        assert len(ALL_TOOLS) == 29

    def test_tool_names(self):
        names = {t.name for t in ALL_TOOLS}
        expected = {
            "get_my_performance", "get_top_rankings", "compare_to_top",
            "get_fight_details", "get_progression", "get_deaths_and_mechanics",
            "get_raid_summary", "search_fights", "get_spec_leaderboard",
            "compare_raid_to_top", "compare_two_raids", "get_raid_execution",
            "get_ability_breakdown", "get_buff_analysis",
            "get_death_analysis", "get_activity_report", "get_cooldown_efficiency",
            "get_consumable_check", "get_overheal_analysis", "get_cancelled_casts",
            "get_resource_usage", "get_cooldown_windows", "get_phase_breakdown",
            "get_dot_analysis", "get_rotation_score",
            "get_trinket_procs", "get_raid_buff_coverage",
            "get_gear_audit", "get_threat_analysis",
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_top_rankings.ainvoke(
                {"encounter_name": "Gruul", "class_name": "Rogue", "spec_name": "Combat"}
            )

        assert "TopRogue" in result


class TestGetRaidSummary:
    async def test_returns_formatted_string(self):
        mock_rows = [
            MagicMock(
                fight_id=1, encounter_name="High King Maulgar",
                kill=True, duration_ms=180000, player_count=25,
            ),
            MagicMock(
                fight_id=2, encounter_name="Gruul",
                kill=True, duration_ms=160000, player_count=25,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_raid_summary.ainvoke({"report_code": "abc123"})

        assert "Gruul" in result


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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await compare_raid_to_top.ainvoke({"report_code": "abc123"})

        assert "Patchwerk" in result
        assert "abc123" in result
        assert "Gap" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_raid_execution.ainvoke({"report_code": "abc123"})

        assert "Patchwerk" in result
        assert "abc123" in result
        assert "Deaths" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_raid_execution.ainvoke({"report_code": "missing"})

        assert "no" in result.lower() or "not found" in result.lower()


class TestToolErrorHandling:
    async def test_db_error_returns_friendly_message(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "Gruul", "player_name": "Test"}
            )

        assert "Error" in result
        assert "connection lost" in result

    async def test_db_error_on_raid_summary(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("timeout")

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_raid_summary.ainvoke({"report_code": "abc123"})

        assert "Error" in result
        assert "timeout" in result

    async def test_db_error_on_compare_raid_to_top(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection refused")

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_ability_breakdown.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "table data" in result.lower() or "not have been ingested" in result.lower()

    async def test_error_handling(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("db error")

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
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

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_buff_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "table data" in result.lower() or "not have been ingested" in result.lower()


class TestGetResourceUsage:
    async def test_returns_resource_data(self):
        mock_rows = [
            MagicMock(
                player_name="TestPriest",
                resource_type="mana",
                min_value=500,
                max_value=10000,
                avg_value=6000.0,
                time_at_zero_ms=3000,
                time_at_zero_pct=2.5,
                samples_json='[{"t":0,"v":10000}]',
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_resource_usage.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestPriest"}
            )

        assert "MANA" in result
        assert "6000" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_resource_usage.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not" in result.lower()


class TestGetCooldownWindows:
    async def test_returns_window_data(self):
        mock_rows = [
            MagicMock(
                player_name="TestWarr",
                ability_name="Death Wish",
                spell_id=12292,
                window_start_ms=5000,
                window_end_ms=35000,
                window_damage=150000,
                window_dps=5000.0,
                baseline_dps=3000.0,
                dps_gain_pct=66.7,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_cooldown_windows.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestWarr"}
            )

        assert "Death Wish" in result
        assert "GREAT" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_cooldown_windows.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not" in result.lower()


class TestGetPhaseBreakdown:
    async def test_returns_phase_data(self):
        mock_rows = [
            MagicMock(
                player_name="TestWarr",
                phase_name="Phase 1",
                phase_start_ms=0,
                phase_end_ms=60000,
                is_downtime=False,
                phase_dps=2500.0,
                phase_casts=40,
                phase_gcd_uptime_pct=92.0,
            ),
            MagicMock(
                player_name="TestWarr",
                phase_name="Transition",
                phase_start_ms=60000,
                phase_end_ms=80000,
                is_downtime=True,
                phase_dps=500.0,
                phase_casts=5,
                phase_gcd_uptime_pct=30.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_phase_breakdown.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestWarr"}
            )

        assert "Phase 1" in result
        assert "DOWNTIME" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_phase_breakdown.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not" in result.lower()


class TestGetDotAnalysis:
    async def test_returns_dot_data(self):
        mock_rows = [
            MagicMock(
                player_name="TestLock",
                spell_id=172,
                ability_name="Corruption",
                total_refreshes=20,
                early_refreshes=3,
                early_refresh_pct=15.0,
                avg_remaining_ms=5000.0,
                clipped_ticks_est=4,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_dot_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestLock"}
            )

        assert "Corruption" in result
        assert "FAIR" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_dot_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not" in result.lower()


class TestGetRotationScore:
    async def test_returns_score_data(self):
        mock_row = MagicMock()
        mock_row.player_name = "TestWarr"
        mock_row.spec = "Fury"
        mock_row.score_pct = 85.0
        mock_row.rules_checked = 5
        mock_row.rules_passed = 4
        mock_row.violations_json = '[{"rule":"Heroic Strike","detail":"Low priority usage"}]'
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_rotation_score.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestWarr"}
            )

        assert "Fury" in result
        assert "B" in result
        assert "4/5" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_rotation_score.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not" in result.lower()


class TestGetTrinketProcs:
    async def test_returns_trinket_data(self):
        mock_rows = [
            MagicMock(
                player_name="TestWarr",
                ability_name="Dragonspine Trophy",
                spell_id=34775,
                uptime_pct=32.5,
                stack_count=0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_trinket_procs.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestWarr"}
            )

        assert "Dragonspine Trophy" in result
        assert "GOOD" in result

    async def test_no_trinkets_detected(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_trinket_procs.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Test"}
            )

        assert "no known trinket" in result.lower() or "not" in result.lower()


class TestGetRaidBuffCoverage:
    async def test_returns_buff_coverage(self):
        mock_rows = [
            MagicMock(
                ability_name="Battle Shout",
                spell_id=2048,
                players_with_buff=20,
                avg_uptime_pct=85.0,
                total_players=25,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_raid_buff_coverage.ainvoke(
                {"report_code": "abc123", "fight_id": 1}
            )

        assert "Battle Shout" in result
        assert "20/25" in result

    async def test_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_raid_buff_coverage.ainvoke(
                {"report_code": "abc123", "fight_id": 1}
            )

        assert "no" in result.lower() or "not" in result.lower()


class TestGetGearAudit:
    async def test_returns_stub_message(self):
        result = await get_gear_audit.ainvoke(
            {"report_code": "abc123", "fight_id": 1, "player_name": "Test"}
        )

        assert "not yet available" in result.lower()
        assert "combatantInfo" in result


class TestGetThreatAnalysis:
    async def test_returns_tank_metrics(self):
        mock_rows = [
            MagicMock(
                player_name="TestTank",
                player_class="Warrior",
                player_spec="Protection",
                dps=500.0,
                hps=200.0,
                deaths=0,
                interrupts=5,
                dispels=0,
                item_level=142.0,
                kill=True,
                duration_ms=180000,
                encounter_name="Patchwerk",
                report_title="Naxx Clear",
                parse_percentile=75.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        # Second call for death details
        mock_death_result = MagicMock()
        mock_death_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.side_effect = [mock_result, mock_death_result]

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_threat_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "TestTank"}
            )

        assert "TestTank" in result
        assert "Protection" in result
        assert "DPS: 500.0" in result

    async def test_player_not_found(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_threat_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1, "player_name": "Nobody"}
            )

        assert "no data" in result.lower() or "not found" in result.lower()


class TestNoResults:
    async def test_get_my_performance_no_data(self):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_my_performance.ainvoke(
                {"encounter_name": "Gruul", "player_name": "Nobody"}
            )

        assert "no" in result.lower() or "not found" in result.lower()
