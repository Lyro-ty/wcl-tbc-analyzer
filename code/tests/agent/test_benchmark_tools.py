"""Tests for benchmark agent tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.agent.tools import get_encounter_benchmarks, get_spec_benchmark

SAMPLE_BENCHMARKS = {
    "kill_stats": {
        "kill_count": 15,
        "avg_duration_ms": 245000,
        "median_duration_ms": 240000,
        "min_duration_ms": 198000,
    },
    "deaths": {
        "avg_deaths": 0.3,
        "zero_death_pct": 80.0,
    },
    "by_spec": {
        "Destruction Warlock": {
            "dps": {
                "sample_size": 5,
                "avg_dps": 1420.0,
                "median_dps": 1380.0,
                "p75_dps": 1520.0,
                "avg_hps": 0.0,
                "median_hps": 0.0,
                "p75_hps": 0.0,
            },
            "gcd": {
                "avg_gcd_uptime": 91.0,
                "avg_cpm": 28.5,
            },
            "abilities": [
                {"ability_name": "Shadow Bolt", "avg_damage_pct": 0.62},
            ],
            "buffs": [
                {"buff_name": "Curse of the Elements", "avg_uptime": 95.0},
            ],
            "cooldowns": [
                {"ability_name": "Infernal", "avg_uses": 1.2, "avg_efficiency": 85.0},
            ],
        },
    },
    "consumables": [
        {"category": "flask", "usage_pct": 0.95,
         "players_with": 14, "total_player_fights": 15},
        {"category": "food", "usage_pct": 0.98,
         "players_with": 15, "total_player_fights": 15},
    ],
    "composition": [
        {"class": "Warlock", "spec": "Destruction", "avg_count": 2.5},
    ],
}


def _make_row(benchmarks=None, encounter_name="Gruul the Dragonkiller", sample_size=15):
    """Build a mock DB row for GET_ENCOUNTER_BENCHMARK."""
    row = MagicMock()
    row.encounter_name = encounter_name
    row.sample_size = sample_size
    row.benchmarks = benchmarks if benchmarks is not None else SAMPLE_BENCHMARKS
    return row


class TestGetEncounterBenchmarks:
    async def test_returns_formatted_text(self):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = _make_row()

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_encounter_benchmarks.ainvoke(
                {"encounter_name": "Gruul"}
            )

        assert "Gruul the Dragonkiller" in result
        assert "15 kills" in result
        # Kill stats
        assert "4m 5s" in result   # avg 245000ms
        assert "4m 0s" in result   # median 240000ms
        assert "3m 18s" in result  # fastest 198000ms
        # Deaths
        assert "0.3" in result
        assert "80%" in result
        # Consumables
        assert "flask" in result
        assert "95%" in result
        # Composition
        assert "Warlock Destruction" in result
        assert "2.5" in result
        # Spec DPS
        assert "1,420.0 DPS" in result
        assert "GCD: 91%" in result
        assert "CPM: 28.5" in result

    async def test_returns_no_data_message(self):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_encounter_benchmarks.ainvoke(
                {"encounter_name": "Nonexistent Boss"}
            )

        assert "No benchmark data found" in result
        assert "Nonexistent Boss" in result

    async def test_handles_json_string_benchmarks(self):
        """WCL JSON scalar pattern: benchmarks may be a JSON string."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = _make_row(
            benchmarks=json.dumps(SAMPLE_BENCHMARKS)
        )

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_encounter_benchmarks.ainvoke(
                {"encounter_name": "Gruul"}
            )

        assert "Gruul the Dragonkiller" in result
        assert "1,420.0 DPS" in result

    async def test_handles_empty_optional_sections(self):
        """Tool should handle missing optional sections gracefully."""
        minimal = {
            "kill_stats": {"avg_duration_ms": 120000, "median_duration_ms": 115000,
                           "min_duration_ms": 100000},
            "deaths": {"avg_deaths": 0.1, "zero_death_pct": 95.0},
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = _make_row(benchmarks=minimal)

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_encounter_benchmarks.ainvoke(
                {"encounter_name": "Gruul"}
            )

        assert "Kill Stats" in result
        assert "Deaths" in result
        # Optional sections should be absent
        assert "Consumable Usage" not in result
        assert "Common Specs" not in result
        assert "Spec DPS Targets" not in result


class TestGetSpecBenchmark:
    async def test_returns_spec_targets(self):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = _make_row()

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_spec_benchmark.ainvoke(
                {
                    "encounter_name": "Gruul",
                    "class_name": "Warlock",
                    "spec_name": "Destruction",
                }
            )

        assert "Destruction Warlock" in result
        assert "Gruul the Dragonkiller" in result
        # Performance targets
        assert "1,420.0" in result
        assert "1,380.0" in result
        assert "1,520.0" in result
        # Activity
        assert "91.0%" in result
        assert "28.5" in result
        # Top abilities
        assert "Shadow Bolt" in result
        assert "62.0%" in result
        # Buff uptimes
        assert "Curse of the Elements" in result
        assert "95.0%" in result
        # Cooldown efficiency
        assert "Infernal" in result
        assert "85%" in result

    async def test_returns_no_benchmark_message(self):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_spec_benchmark.ainvoke(
                {
                    "encounter_name": "Unknown",
                    "class_name": "Warrior",
                    "spec_name": "Arms",
                }
            )

        assert "No benchmark data found" in result

    async def test_returns_available_specs_for_missing_spec(self):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = _make_row()

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_spec_benchmark.ainvoke(
                {
                    "encounter_name": "Gruul",
                    "class_name": "Warrior",
                    "spec_name": "Arms",
                }
            )

        assert "No benchmark data for Arms Warrior" in result
        assert "Available specs:" in result
        assert "Destruction Warlock" in result

    async def test_handles_json_string_benchmarks(self):
        """benchmarks column may be a JSON string."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = _make_row(
            benchmarks=json.dumps(SAMPLE_BENCHMARKS)
        )

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_spec_benchmark.ainvoke(
                {
                    "encounter_name": "Gruul",
                    "class_name": "Warlock",
                    "spec_name": "Destruction",
                }
            )

        assert "1,420.0" in result
        assert "Shadow Bolt" in result
