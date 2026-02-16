"""Tests for the speed rankings ingestion pipeline."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from shukketsu.pipeline.speed_rankings import (
    SpeedRankingsResult,
    fetch_speed_rankings_for_encounter,
    ingest_all_speed_rankings,
    parse_speed_rankings,
)

SAMPLE_SPEED_DATA = {
    "rankings": [
        {
            "fightID": 10,
            "duration": 120000,
            "report": {
                "code": "abc123",
                "guild": {"name": "Speed Guild"},
            },
        },
        {
            "fightID": 15,
            "duration": 125000,
            "report": {
                "code": "def456",
                "guild": None,
            },
        },
    ],
    "page": 1,
    "hasMorePages": False,
}


class TestParseSpeedRankings:
    def test_parses_rankings(self):
        result = parse_speed_rankings(SAMPLE_SPEED_DATA, 201107)
        assert len(result) == 2

    def test_sets_fields_correctly(self):
        result = parse_speed_rankings(SAMPLE_SPEED_DATA, 201107)
        first = result[0]
        assert first.encounter_id == 201107
        assert first.rank_position == 1
        assert first.report_code == "abc123"
        assert first.fight_id == 10
        assert first.duration_ms == 120000
        assert first.guild_name == "Speed Guild"

    def test_sequential_rank_position(self):
        result = parse_speed_rankings(SAMPLE_SPEED_DATA, 201107)
        positions = [r.rank_position for r in result]
        assert positions == [1, 2]

    def test_handles_none_guild(self):
        result = parse_speed_rankings(SAMPLE_SPEED_DATA, 201107)
        second = result[1]
        assert second.guild_name is None

    def test_empty_rankings(self):
        result = parse_speed_rankings({"rankings": []}, 201107)
        assert result == []

    def test_none_data(self):
        result = parse_speed_rankings(None, 201107)
        assert result == []

    def test_caps_at_100(self):
        data = {
            "rankings": [
                {
                    "fightID": i,
                    "duration": 120000,
                    "report": {"code": f"r{i}", "guild": None},
                }
                for i in range(120)
            ]
        }
        result = parse_speed_rankings(data, 201107)
        assert len(result) == 100

    def test_handles_json_string(self):
        json_str = json.dumps(SAMPLE_SPEED_DATA)
        result = parse_speed_rankings(json_str, 201107)
        assert len(result) == 2

    def test_handles_missing_report(self):
        data = {
            "rankings": [
                {
                    "fightID": 1,
                    "duration": 100000,
                }
            ]
        }
        result = parse_speed_rankings(data, 201107)
        assert len(result) == 1
        assert result[0].report_code == ""
        assert result[0].guild_name is None


class TestSpeedRankingsResult:
    def test_defaults(self):
        r = SpeedRankingsResult()
        assert r.fetched == 0
        assert r.skipped == 0
        assert r.errors == []


class TestFetchSpeedRankingsForEncounter:
    async def test_calls_wcl_with_correct_variables(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "fightRankings": SAMPLE_SPEED_DATA,
                }
            }
        }
        session = AsyncMock()

        count = await fetch_speed_rankings_for_encounter(wcl, session, 201107)

        assert count == 2
        wcl.query.assert_called_once()
        call_vars = wcl.query.call_args[1]["variables"]
        assert call_vars["encounterID"] == 201107
        assert call_vars["page"] == 1

    async def test_deletes_old_data(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "fightRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        await fetch_speed_rankings_for_encounter(wcl, session, 201107)

        # Should have called execute once for the DELETE
        assert session.execute.call_count == 1

    async def test_adds_rankings_to_session(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "fightRankings": SAMPLE_SPEED_DATA,
                }
            }
        }
        session = AsyncMock()

        await fetch_speed_rankings_for_encounter(wcl, session, 201107)

        assert session.add.call_count == 2


class TestIngestAllSpeedRankings:
    async def test_fetches_all_encounters(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "fightRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        result = await ingest_all_speed_rankings(
            wcl, session, [201107, 201108], force=True
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

        result = await ingest_all_speed_rankings(
            wcl, session, [201107], force=False, stale_hours=24
        )

        assert result.skipped == 1
        assert result.fetched == 0
        wcl.query.assert_not_called()

    async def test_force_overrides_staleness(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "fightRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        result = await ingest_all_speed_rankings(
            wcl, session, [201107], force=True
        )

        assert result.fetched == 1
        wcl.query.assert_called_once()

    async def test_commits_per_encounter(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "encounter": {
                    "fightRankings": {"rankings": []},
                }
            }
        }
        session = AsyncMock()

        await ingest_all_speed_rankings(
            wcl, session, [201107, 201108], force=True
        )

        assert session.commit.call_count == 2

    async def test_collects_errors(self):
        wcl = AsyncMock()
        wcl.query.side_effect = [
            Exception("API error"),
            {
                "worldData": {
                    "encounter": {
                        "fightRankings": {"rankings": []},
                    }
                }
            },
        ]
        session = AsyncMock()

        result = await ingest_all_speed_rankings(
            wcl, session, [201107, 201108], force=True
        )

        assert result.fetched == 1
        assert len(result.errors) == 1
        assert "201107" in result.errors[0]
