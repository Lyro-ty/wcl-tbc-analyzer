"""Tests for encounter seeding functions."""

from unittest.mock import AsyncMock

from shukketsu.pipeline.seeds import discover_and_seed_encounters, seed_encounters_from_list


class TestSeedEncountersFromList:
    async def test_creates_encounters(self):
        session = AsyncMock()
        encounters = [
            {"id": 100, "name": "Boss A", "zone_id": 10, "zone_name": "Zone X", "difficulty": 0},
            {"id": 101, "name": "Boss B", "zone_id": 10, "zone_name": "Zone X", "difficulty": 0},
        ]
        count = await seed_encounters_from_list(session, encounters)
        assert count == 2
        assert session.merge.call_count == 2
        session.flush.assert_called_once()

    async def test_empty_list(self):
        session = AsyncMock()
        count = await seed_encounters_from_list(session, [])
        assert count == 0

    async def test_idempotent(self):
        """merge() handles duplicate IDs gracefully."""
        session = AsyncMock()
        encounters = [
            {"id": 100, "name": "Boss A", "zone_id": 10, "zone_name": "Zone X"},
        ]
        await seed_encounters_from_list(session, encounters)
        await seed_encounters_from_list(session, encounters)
        assert session.merge.call_count == 2  # Called once per invocation


class TestDiscoverAndSeedEncounters:
    async def test_discovers_from_wcl(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {
                "zone": {
                    "name": "Test Zone",
                    "encounters": [
                        {"id": 200, "name": "Boss X"},
                        {"id": 201, "name": "Boss Y"},
                    ],
                }
            }
        }
        session = AsyncMock()
        result = await discover_and_seed_encounters(wcl, session, [42])
        assert len(result) == 2
        assert result[0]["name"] == "Boss X"
        assert result[0]["zone_id"] == 42
        assert result[0]["zone_name"] == "Test Zone"

    async def test_handles_unknown_zone(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "worldData": {"zone": None}
        }
        session = AsyncMock()
        result = await discover_and_seed_encounters(wcl, session, [9999])
        assert len(result) == 0

    async def test_multiple_zones(self):
        wcl = AsyncMock()
        wcl.query.side_effect = [
            {
                "worldData": {
                    "zone": {
                        "name": "Zone A",
                        "encounters": [{"id": 1, "name": "B1"}],
                    }
                }
            },
            {
                "worldData": {
                    "zone": {
                        "name": "Zone B",
                        "encounters": [{"id": 2, "name": "B2"}],
                    }
                }
            },
        ]
        session = AsyncMock()
        result = await discover_and_seed_encounters(wcl, session, [10, 20])
        assert len(result) == 2
