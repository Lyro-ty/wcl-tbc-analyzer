"""Tests for get_phase_analysis agent tool."""

from unittest.mock import AsyncMock, MagicMock, patch


class TestGetPhaseAnalysis:
    async def test_returns_phase_info_for_known_encounter(self):
        """Tool should include phase definitions for known encounters."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=4, duration_ms=300000, kill=True,
                fight_percentage=0.0, encounter_name="Prince Malchezaar",
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=2500.0, total_damage=750000, hps=0.0, total_healing=0,
                deaths=0, parse_percentile=92.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        assert "Prince Malchezaar" in result
        assert "P1 - Normal" in result
        assert "P2 - Axes" in result
        assert "P3 - Infernals" in result
        assert "Lyro" in result

    async def test_returns_single_phase_for_unknown_encounter(self):
        """Unknown encounters should default to a single 'Full Fight' phase."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=1, duration_ms=120000, kill=True,
                fight_percentage=0.0, encounter_name="Unknown Boss",
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=1800.0, total_damage=216000, hps=0.0, total_healing=0,
                deaths=0, parse_percentile=80.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 1}
            )

        assert "Full Fight" in result
        assert "Unknown Boss" in result

    async def test_includes_estimated_phase_durations(self):
        """Phase durations should be estimated from total fight duration."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=4, duration_ms=200000, kill=True,
                fight_percentage=0.0, encounter_name="Magtheridon",
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=2000.0, total_damage=400000, hps=0.0, total_healing=0,
                deaths=0, parse_percentile=85.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        # Magtheridon P1: 0.0-0.3 of 200s = 0-60s = 1m 0s
        # Magtheridon P2: 0.3-1.0 of 200s = 60-200s = 2m 20s
        assert "P1 - Channelers" in result
        assert "P2 - Magtheridon" in result
        assert "1m 0s" in result
        assert "2m 20s" in result

    async def test_filters_by_player_name(self):
        """Tool should filter players when player_name is provided."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=4, duration_ms=180000, kill=True,
                fight_percentage=0.0, encounter_name="Moroes",
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=2500.0, total_damage=450000, hps=0.0, total_healing=0,
                deaths=0, parse_percentile=92.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 4, "player_name": "Lyro"}
            )

        assert "Lyro" in result
        # Verify player_name param was passed
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["player_name"] == "%Lyro%"

    async def test_no_data_returns_friendly_message(self):
        """Tool should return a friendly message when fight is not found."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "missing", "fight_id": 99}
            )

        assert "no" in result.lower() or "not found" in result.lower()

    async def test_error_handling(self):
        """Tool should return error string on DB failure."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("connection lost")

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        assert "Error" in result
        assert "connection lost" in result

    async def test_shows_kill_status(self):
        """Tool should show kill/wipe status."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=2, duration_ms=95000, kill=False,
                fight_percentage=35.2, encounter_name="Moroes",
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=1500.0, total_damage=142500, hps=0.0, total_healing=0,
                deaths=1, parse_percentile=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 2}
            )

        assert "Wipe" in result

    async def test_multiple_players_shown(self):
        """Tool should show all players in the fight."""
        mock_rows = [
            MagicMock(
                report_code="abc123", fight_id=4, duration_ms=180000, kill=True,
                fight_percentage=0.0, encounter_name="Moroes",
                player_name="Lyro", player_class="Warrior", player_spec="Arms",
                dps=2500.0, total_damage=450000, hps=0.0, total_healing=0,
                deaths=0, parse_percentile=92.0,
            ),
            MagicMock(
                report_code="abc123", fight_id=4, duration_ms=180000, kill=True,
                fight_percentage=0.0, encounter_name="Moroes",
                player_name="Healer", player_class="Priest", player_spec="Holy",
                dps=200.0, total_damage=36000, hps=1500.0, total_healing=270000,
                deaths=0, parse_percentile=85.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.agent.tools import get_phase_analysis

        with patch("shukketsu.agent.tool_utils._get_session", return_value=mock_session):
            result = await get_phase_analysis.ainvoke(
                {"report_code": "abc123", "fight_id": 4}
            )

        assert "Lyro" in result
        assert "Healer" in result


class TestGetPhaseAnalysisInAllTools:
    def test_phase_analysis_in_all_tools(self):
        """get_phase_analysis should be in ALL_TOOLS."""
        from shukketsu.agent.tools import ALL_TOOLS

        names = {t.name for t in ALL_TOOLS}
        assert "get_phase_analysis" in names

    def test_tool_count_updated(self):
        """ALL_TOOLS should include the new tool."""
        from shukketsu.agent.tools import ALL_TOOLS

        assert len(ALL_TOOLS) == 30
