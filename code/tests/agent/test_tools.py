from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from shukketsu.agent.tools import (
    get_my_performance,
    get_top_rankings,
    compare_to_top,
    get_fight_details,
    get_progression,
    get_deaths_and_mechanics,
    get_raid_summary,
    search_fights,
    ALL_TOOLS,
)


class TestToolDecorators:
    def test_all_tools_are_base_tool(self):
        for tool in ALL_TOOLS:
            assert isinstance(tool, BaseTool), f"{tool.name} is not a BaseTool"

    def test_all_tools_have_docstrings(self):
        for tool in ALL_TOOLS:
            assert tool.description, f"{tool.name} has no description"

    def test_expected_tool_count(self):
        assert len(ALL_TOOLS) == 8

    def test_tool_names(self):
        names = {t.name for t in ALL_TOOLS}
        expected = {
            "get_my_performance", "get_top_rankings", "compare_to_top",
            "get_fight_details", "get_progression", "get_deaths_and_mechanics",
            "get_raid_summary", "search_fights",
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
