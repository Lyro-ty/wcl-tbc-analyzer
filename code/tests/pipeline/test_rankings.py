"""Tests for the top rankings ingestion pipeline."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shukketsu.pipeline.rankings import (
    RankingsResult,
    fetch_rankings_for_spec,
    ingest_all_rankings,
    parse_zone_rankings,
)

SAMPLE_RANKINGS_DATA = {
    "rankings": [
        {
            "name": "TopRogue",
            "class": 4,
            "spec": "Combat",
            "amount": 2000.5,
            "duration": 150000,
            "server": {"name": "Faerlina"},
            "reportCode": "abc123",
            "fightID": 5,
            "guild": {"name": "Top Guild"},
            "bracketData": 146,
            "total": 300075,
        },
        {
            "name": "SecondRogue",
            "class": 4,
            "spec": "Combat",
            "amount": 1900.3,
            "duration": 155000,
            "server": {"name": "Whitemane"},
            "reportCode": "def456",
            "fightID": 3,
            "guild": None,
            "bracketData": 142,
            "total": 294547,
        },
    ],
    "page": 1,
    "hasMorePages": False,
}


class TestParseZoneRankings:
    def test_parses_rankings(self):
        result = parse_zone_rankings(
            SAMPLE_RANKINGS_DATA, 650, "Rogue", "Combat", "dps"
        )
        assert len(result) == 2

    def test_sets_fields_correctly(self):
        result = parse_zone_rankings(
            SAMPLE_RANKINGS_DATA, 650, "Rogue", "Combat", "dps"
        )
        first = result[0]
        assert first.encounter_id == 650
        assert first.class_ == "Rogue"
        assert first.spec == "Combat"
        assert first.metric == "dps"
        assert first.rank_position == 1
        assert first.player_name == "TopRogue"
        assert first.player_server == "Faerlina"
        assert first.amount == pytest.approx(2000.5)
        assert first.duration_ms == 150000
        assert first.report_code == "abc123"
        assert first.fight_id == 5
        assert first.guild_name == "Top Guild"
        assert first.item_level == pytest.approx(146)

    def test_sequential_rank_position(self):
        result = parse_zone_rankings(
            SAMPLE_RANKINGS_DATA, 650, "Rogue", "Combat", "dps"
        )
        positions = [r.rank_position for r in result]
        assert positions == [1, 2]

    def test_handles_none_guild(self):
        result = parse_zone_rankings(
            SAMPLE_RANKINGS_DATA, 650, "Rogue", "Combat", "dps"
        )
        second = result[1]
        assert second.guild_name is None

    def test_empty_rankings(self):
        result = parse_zone_rankings(
            {"rankings": []}, 650, "Rogue", "Combat", "dps"
        )
        assert result == []

    def test_none_data(self):
        result = parse_zone_rankings(None, 650, "Rogue", "Combat", "dps")
        assert result == []

    def test_caps_at_50(self):
        data = {
            "rankings": [
                {
                    "name": f"Player{i}",
                    "class": 4,
                    "spec": "Combat",
                    "amount": 1000.0,
                    "duration": 150000,
                    "server": {"name": "S"},
                    "reportCode": "x",
                    "fightID": 1,
                    "guild": None,
                    "bracketData": 140,
                    "total": 150000,
                }
                for i in range(60)
            ]
        }
        result = parse_zone_rankings(data, 650, "Rogue", "Combat", "dps")
        assert len(result) == 50

    def test_handles_json_string(self):
        json_str = json.dumps(SAMPLE_RANKINGS_DATA)
        result = parse_zone_rankings(json_str, 650, "Rogue", "Combat", "dps")
        assert len(result) == 2

    def test_missing_optional_fields(self):
        data = {
            "rankings": [
                {
                    "name": "Minimal",
                    "class": 1,
                    "spec": "Arms",
                    "amount": 500.0,
                    "duration": 120000,
                    "reportCode": "xyz",
                    "fightID": 1,
                }
            ]
        }
        result = parse_zone_rankings(data, 100, "Warrior", "Arms", "dps")
        assert len(result) == 1
        assert result[0].player_server == ""
        assert result[0].guild_name is None
        assert result[0].item_level is None


class TestRankingsResult:
    def test_defaults(self):
        r = RankingsResult()
        assert r.fetched == 0
        assert r.skipped == 0
        assert r.errors == []


class TestFetchRankingsForSpec:
    async def test_calls_wcl_with_correct_variables(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": SAMPLE_RANKINGS_DATA,
                }
            }
        }
        session = AsyncMock()

        count = await fetch_rankings_for_spec(
            wcl, session, 650, "Rogue", "Combat", "dps"
        )

        assert count == 2
        wcl.query.assert_called_once()
        call_vars = wcl.query.call_args[1]["variables"]
        assert call_vars["encounterID"] == 650
        assert call_vars["className"] == "Rogue"
        assert call_vars["specName"] == "Combat"
        assert call_vars["metric"] == "dps"
        assert call_vars["page"] == 1

    async def test_deletes_old_data(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        await fetch_rankings_for_spec(
            wcl, session, 650, "Rogue", "Combat", "dps"
        )

        # Should have called execute once for the DELETE
        assert session.execute.call_count == 1

    async def test_returns_zero_for_empty_rankings(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        count = await fetch_rankings_for_spec(
            wcl, session, 650, "Rogue", "Combat", "dps"
        )

        assert count == 0

    async def test_adds_rankings_to_session(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": SAMPLE_RANKINGS_DATA,
                }
            }
        }
        session = AsyncMock()

        await fetch_rankings_for_spec(
            wcl, session, 650, "Rogue", "Combat", "dps"
        )

        # 2 rankings added via session.add
        assert session.add.call_count == 2


class TestIngestAllRankings:
    @dataclass(frozen=True)
    class MockSpec:
        class_name: str
        spec_name: str
        role: str

    async def test_fetches_all_combos(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()
        # Mock the staleness check to return None (never fetched)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        result = await ingest_all_rankings(
            wcl, session, [650, 651], specs, force=True
        )

        assert result.fetched == 2
        assert result.skipped == 0
        assert wcl.query.call_count == 2

    async def test_skips_fresh_data(self):
        wcl = AsyncMock()
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = datetime.now(UTC)
        session.execute.return_value = mock_result

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        result = await ingest_all_rankings(
            wcl, session, [650], specs, force=False, stale_hours=24
        )

        assert result.skipped == 1
        assert result.fetched == 0
        wcl.query.assert_not_called()

    async def test_force_overrides_staleness(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        result = await ingest_all_rankings(
            wcl, session, [650], specs, force=True
        )

        assert result.fetched == 1
        wcl.query.assert_called_once()

    async def test_continues_on_error(self):
        wcl = AsyncMock()
        wcl.query.side_effect = [
            Exception("API error"),
            {
                "worldData": {
                    "encounter": {
                        "characterRankings": {"rankings": []},
                    }
                }
            },
        ]
        session = AsyncMock()

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        result = await ingest_all_rankings(
            wcl, session, [650, 651], specs, force=True
        )

        assert result.fetched == 1
        assert len(result.errors) == 1

    async def test_commits_per_encounter_batch(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        await ingest_all_rankings(
            wcl, session, [650, 651], specs, force=True
        )

        assert session.commit.call_count == 2  # Once per encounter

    async def test_include_hps_for_healers(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        specs = [self.MockSpec("Priest", "Holy", "healer")]
        result = await ingest_all_rankings(
            wcl, session, [650], specs, include_hps=True, force=True
        )

        # Should fetch both DPS and HPS for healer spec
        assert result.fetched == 2
        assert wcl.query.call_count == 2

    async def test_no_hps_for_dps_spec(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "characterRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        result = await ingest_all_rankings(
            wcl, session, [650], specs, include_hps=True, force=True
        )

        # Should only fetch DPS for non-healer
        assert result.fetched == 1
        assert wcl.query.call_count == 1

    async def test_error_message_format(self):
        wcl = AsyncMock()
        wcl.query.side_effect = Exception("rate limited")
        session = AsyncMock()

        specs = [self.MockSpec("Rogue", "Combat", "dps")]
        result = await ingest_all_rankings(
            wcl, session, [650], specs, force=True
        )

        assert len(result.errors) == 1
        assert "Rogue" in result.errors[0]
        assert "Combat" in result.errors[0]
        assert "650" in result.errors[0]
        assert "rate limited" in result.errors[0]
