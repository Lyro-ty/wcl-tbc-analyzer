"""Tests for death events pipeline (parse + ingest)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.pipeline.death_events import (
    ingest_death_events_for_fight,
    parse_death_events,
)


class TestParseDeathEventsBasic:
    def test_single_death_event(self):
        """Single death event produces correct DeathDetail fields."""
        events = [
            {
                "timestamp": 45000,
                "sourceID": 1,
                "source": {"name": "Patchwerk", "id": 1, "type": "NPC"},
                "targetID": 5,
                "target": {"name": "Lyro", "id": 5},
                "ability": {"name": "Hateful Strike", "guid": 28308},
                "killingBlow": True,
                "fight": 3,
                "hitPoints": 0,
                "events": [
                    {
                        "timestamp": 43000,
                        "source": {"name": "Patchwerk"},
                        "ability": {"name": "Melee", "guid": 1},
                        "amount": 4000,
                        "type": "damage",
                    },
                    {
                        "timestamp": 44000,
                        "source": {"name": "Patchwerk"},
                        "ability": {"name": "Hateful Strike", "guid": 28308},
                        "amount": 8000,
                        "type": "damage",
                    },
                ],
            }
        ]

        result = parse_death_events(events, fight_id=42)

        assert len(result) == 1
        detail = result[0]
        assert detail.fight_id == 42
        assert detail.player_name == "Lyro"
        assert detail.death_index == 0
        assert detail.timestamp_ms == 45000
        assert detail.killing_blow_ability == "Hateful Strike"
        assert detail.killing_blow_source == "Patchwerk"
        assert detail.damage_taken_total == 12000
        # Verify events_json
        parsed_events = json.loads(detail.events_json)
        assert len(parsed_events) == 2
        assert parsed_events[0]["ts"] == 43000
        assert parsed_events[0]["ability"] == "Melee"
        assert parsed_events[0]["amount"] == 4000
        assert parsed_events[0]["source"] == "Patchwerk"
        assert parsed_events[1]["ts"] == 44000
        assert parsed_events[1]["ability"] == "Hateful Strike"
        assert parsed_events[1]["amount"] == 8000


class TestParseDeathEventsMultipleDeathsSamePlayer:
    def test_death_index_increments(self):
        """When a player dies multiple times, death_index increments per player."""
        events = [
            {
                "timestamp": 10000,
                "target": {"name": "Lyro"},
                "ability": {"name": "Melee"},
                "source": {"name": "Boss"},
                "events": [
                    {"timestamp": 9000, "source": {"name": "Boss"},
                     "ability": {"name": "Melee"}, "amount": 5000},
                ],
            },
            {
                "timestamp": 30000,
                "target": {"name": "Warrior"},
                "ability": {"name": "Cleave"},
                "source": {"name": "Boss"},
                "events": [],
            },
            {
                "timestamp": 50000,
                "target": {"name": "Lyro"},
                "ability": {"name": "Enrage"},
                "source": {"name": "Boss"},
                "events": [
                    {"timestamp": 49000, "source": {"name": "Boss"},
                     "ability": {"name": "Enrage"}, "amount": 20000},
                ],
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 3
        # First Lyro death
        assert result[0].player_name == "Lyro"
        assert result[0].death_index == 0
        # Warrior death
        assert result[1].player_name == "Warrior"
        assert result[1].death_index == 0
        # Second Lyro death
        assert result[2].player_name == "Lyro"
        assert result[2].death_index == 1


class TestParseDeathEventsEmpty:
    def test_empty_list_returns_empty(self):
        """Empty events list returns empty result."""
        result = parse_death_events([], fight_id=1)
        assert result == []


class TestParseDeathEventsMissingFields:
    def test_missing_target(self):
        """Event with missing target uses 'Unknown' as player_name."""
        events = [
            {
                "timestamp": 5000,
                "ability": {"name": "Shadow Bolt"},
                "source": {"name": "Kel'Thuzad"},
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 1
        assert result[0].player_name == "Unknown"

    def test_missing_ability(self):
        """Event with missing ability uses 'Unknown' as killing_blow_ability."""
        events = [
            {
                "timestamp": 5000,
                "target": {"name": "Lyro"},
                "source": {"name": "Patchwerk"},
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 1
        assert result[0].killing_blow_ability == "Unknown"

    def test_missing_source(self):
        """Event with missing source uses 'Unknown' as killing_blow_source."""
        events = [
            {
                "timestamp": 5000,
                "target": {"name": "Lyro"},
                "ability": {"name": "Void Zone"},
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 1
        assert result[0].killing_blow_source == "Unknown"

    def test_missing_timestamp(self):
        """Event with missing timestamp defaults to 0."""
        events = [
            {
                "target": {"name": "Lyro"},
                "ability": {"name": "Fire"},
                "source": {"name": "Boss"},
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 1
        assert result[0].timestamp_ms == 0

    def test_null_nested_events(self):
        """Event with null nested events produces 0 damage and empty events_json."""
        events = [
            {
                "timestamp": 5000,
                "target": {"name": "Lyro"},
                "ability": {"name": "Fire"},
                "source": {"name": "Boss"},
                "events": None,
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 1
        assert result[0].damage_taken_total == 0
        assert json.loads(result[0].events_json) == []

    def test_nested_events_missing_fields(self):
        """Nested events with missing fields use defaults."""
        events = [
            {
                "timestamp": 5000,
                "target": {"name": "Lyro"},
                "ability": {"name": "Fire"},
                "source": {"name": "Boss"},
                "events": [
                    {},
                    {"amount": 3000},
                ],
            },
        ]

        result = parse_death_events(events, fight_id=1)

        assert len(result) == 1
        assert result[0].damage_taken_total == 3000
        parsed = json.loads(result[0].events_json)
        assert len(parsed) == 2
        assert parsed[0]["ts"] == 0
        assert parsed[0]["ability"] == "Unknown"
        assert parsed[0]["amount"] == 0
        assert parsed[0]["source"] == "Unknown"
        assert parsed[1]["amount"] == 3000

    def test_events_json_limits_to_last_5(self):
        """Only last 5 nested events are included in events_json."""
        nested = [
            {
                "timestamp": i * 1000,
                "source": {"name": "Boss"},
                "ability": {"name": f"Spell-{i}"},
                "amount": 1000,
            }
            for i in range(8)
        ]
        events = [
            {
                "timestamp": 9000,
                "target": {"name": "Lyro"},
                "ability": {"name": "Final"},
                "source": {"name": "Boss"},
                "events": nested,
            },
        ]

        result = parse_death_events(events, fight_id=1)

        parsed = json.loads(result[0].events_json)
        assert len(parsed) == 5
        # Should be the last 5 (indices 3-7)
        assert parsed[0]["ability"] == "Spell-3"
        assert parsed[4]["ability"] == "Spell-7"
        # But damage_taken_total includes all 8
        assert result[0].damage_taken_total == 8000


class TestIngestDeathEventsForFight:
    async def test_mocked_ingest(self):
        """Verify ingest fetches events, parses, and adds to session."""
        wcl = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()

        fight = MagicMock()
        fight.id = 42
        fight.fight_id = 3
        fight.start_time = 0
        fight.end_time = 60000

        death_events = [
            {
                "timestamp": 45000,
                "source": {"name": "Patchwerk"},
                "target": {"name": "Lyro"},
                "ability": {"name": "Hateful Strike"},
                "events": [
                    {
                        "timestamp": 44000,
                        "source": {"name": "Patchwerk"},
                        "ability": {"name": "Hateful Strike"},
                        "amount": 8000,
                    },
                ],
            },
            {
                "timestamp": 50000,
                "source": {"name": "Patchwerk"},
                "target": {"name": "Warrior"},
                "ability": {"name": "Melee"},
                "events": [],
            },
        ]

        async def _fake_fetch(*args, **kwargs):
            yield death_events

        with patch(
            "shukketsu.pipeline.death_events.fetch_all_events",
            side_effect=_fake_fetch,
        ):
            count = await ingest_death_events_for_fight(
                wcl, session, "ABC123", fight,
            )

        assert count == 2
        assert session.add.call_count == 2
        session.flush.assert_awaited_once()

    async def test_empty_events_returns_zero(self):
        """When WCL returns no death events, returns 0 without adding anything."""
        wcl = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock()

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 1
        fight.start_time = 0
        fight.end_time = 60000

        async def _fake_fetch_empty(*args, **kwargs):
            if False:
                yield

        with patch(
            "shukketsu.pipeline.death_events.fetch_all_events",
            side_effect=_fake_fetch_empty,
        ):
            count = await ingest_death_events_for_fight(
                wcl, session, "EMPTY", fight,
            )

        assert count == 0
        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    async def test_exception_returns_zero(self):
        """When fetch_all_events raises, returns 0 without propagating."""
        wcl = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 1
        fight.start_time = 0
        fight.end_time = 60000

        count = await ingest_death_events_for_fight(
            wcl, session, "FAIL", fight,
        )

        assert count == 0
