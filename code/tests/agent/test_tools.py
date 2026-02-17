from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.tools import BaseTool

from shukketsu.agent.tools import (
    ALL_TOOLS,
    compare_raid_to_top,
    compare_two_raids,
    get_ability_breakdown,
    get_buff_analysis,
    get_deaths_and_mechanics,
    get_my_performance,
    get_raid_execution,
    get_raid_summary,
    get_top_rankings,
)


class TestToolDecorators:
    def test_all_tools_are_base_tool(self):
        for tool in ALL_TOOLS:
            assert isinstance(tool, BaseTool), f"{tool.name} is not a BaseTool"

    def test_all_tools_have_docstrings(self):
        for tool in ALL_TOOLS:
            assert tool.description, f"{tool.name} has no description"

    def test_expected_tool_count(self):
        assert len(ALL_TOOLS) == 17

    def test_tool_names(self):
        names = {t.name for t in ALL_TOOLS}
        expected = {
            "get_my_performance", "get_top_rankings", "compare_to_top",
            "get_fight_details", "get_progression", "get_deaths_and_mechanics",
            "get_raid_summary", "search_fights", "get_spec_leaderboard",
            "compare_raid_to_top", "compare_two_raids", "get_raid_execution",
            "get_ability_breakdown", "get_buff_analysis",
            "get_death_analysis", "get_activity_report", "get_cooldown_efficiency",
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
