"""Tests for death event parsing and ingestion."""

import json
from unittest.mock import AsyncMock, MagicMock

from shukketsu.pipeline.event_data import (
    ingest_deaths_for_fight,
    parse_death_events,
)


class TestParseDeathEvents:
    def test_basic_death(self):
        actor_map = {1: "Lyro", 100: "Patchwerk"}
        events = [
            {
                "timestamp": 5000,
                "sourceID": 1,
                "killingAbility": {"name": "Hateful Strike"},
                "killerID": 100,
                "events": [
                    {"timestamp": 3000, "type": "damage", "amount": 5000,
                     "ability": {"name": "Melee"}, "sourceID": 100},
                    {"timestamp": 4000, "type": "damage", "amount": 8000,
                     "ability": {"name": "Hateful Strike"}, "sourceID": 100},
                ],
            }
        ]

        result = parse_death_events(events, fight_start_time=0, actor_name_by_id=actor_map)

        assert len(result) == 1
        death = result[0]
        assert death.player_name == "Lyro"
        assert death.death_index == 1
        assert death.timestamp_ms == 5000
        assert death.killing_blow_ability == "Hateful Strike"
        assert death.killing_blow_source == "Patchwerk"
        assert death.damage_taken_total == 13000

        parsed_events = json.loads(death.events_json)
        assert len(parsed_events) == 2
        assert parsed_events[0]["ability"] == "Melee"
        assert parsed_events[1]["ability"] == "Hateful Strike"

    def test_multiple_deaths_same_player(self):
        actor_map = {1: "Lyro", 100: "Boss"}
        events = [
            {
                "timestamp": 5000, "sourceID": 1,
                "killingAbility": {"name": "Spell A"}, "killerID": 100,
                "events": [],
            },
            {
                "timestamp": 15000, "sourceID": 1,
                "killingAbility": {"name": "Spell B"}, "killerID": 100,
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_start_time=0, actor_name_by_id=actor_map)

        assert len(result) == 2
        assert result[0].death_index == 1
        assert result[0].killing_blow_ability == "Spell A"
        assert result[1].death_index == 2
        assert result[1].killing_blow_ability == "Spell B"

    def test_missing_actor_id(self):
        actor_map = {100: "Boss"}  # Source ID 1 not in map
        events = [
            {
                "timestamp": 5000, "sourceID": 1,
                "killingAbility": {"name": "Fire"}, "killerID": 100,
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_start_time=0, actor_name_by_id=actor_map)

        assert len(result) == 1
        assert result[0].player_name == "Unknown-1"
        assert result[0].killing_blow_source == "Boss"

    def test_no_killing_ability(self):
        actor_map = {1: "Lyro"}
        events = [
            {
                "timestamp": 5000, "sourceID": 1,
                "killingAbility": None, "killerID": None,
                "events": [],
            },
        ]

        result = parse_death_events(events, fight_start_time=0, actor_name_by_id=actor_map)

        assert result[0].killing_blow_ability == "Unknown"
        assert result[0].killing_blow_source == "Environment"

    def test_fight_start_time_offset(self):
        actor_map = {1: "Lyro"}
        events = [
            {
                "timestamp": 105000, "sourceID": 1,
                "killingAbility": {"name": "Hit"}, "killerID": None,
                "events": [
                    {"timestamp": 104000, "type": "damage", "amount": 1000,
                     "ability": {"name": "X"}, "sourceID": 99},
                ],
            },
        ]

        result = parse_death_events(
            events, fight_start_time=100000, actor_name_by_id=actor_map,
        )

        assert result[0].timestamp_ms == 5000  # 105000 - 100000
        parsed = json.loads(result[0].events_json)
        assert parsed[0]["ts"] == 4000  # 104000 - 100000

    def test_last_10_events_limit(self):
        actor_map = {1: "Lyro"}
        sub_events = [
            {"timestamp": i * 100, "type": "damage", "amount": 100,
             "ability": {"name": f"Hit{i}"}, "sourceID": 99}
            for i in range(15)
        ]
        events = [
            {
                "timestamp": 5000, "sourceID": 1,
                "killingAbility": {"name": "Kill"}, "killerID": 99,
                "events": sub_events,
            },
        ]

        result = parse_death_events(events, fight_start_time=0, actor_name_by_id=actor_map)

        parsed = json.loads(result[0].events_json)
        assert len(parsed) == 10
        # Should be the LAST 10
        assert parsed[0]["ability"] == "Hit5"

    def test_empty_events(self):
        result = parse_death_events([], fight_start_time=0, actor_name_by_id={})
        assert result == []


class TestIngestDeathsForFight:
    async def test_mocked_ingest(self):
        wcl = AsyncMock()
        session = AsyncMock()

        # Mock the delete operation
        session.execute = AsyncMock()

        death_events = [
            {
                "timestamp": 5000, "sourceID": 1,
                "killingAbility": {"name": "Hit"}, "killerID": 100,
                "events": [],
            },
        ]
        wcl.query = AsyncMock(return_value={
            "reportData": {
                "report": {
                    "events": {
                        "data": death_events,
                        "nextPageTimestamp": None,
                    }
                }
            }
        })

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 5
        fight.start_time = 0
        fight.end_time = 10000
        fight.report_code = "ABC"

        actor_map = {1: "Lyro", 100: "Boss"}

        count = await ingest_deaths_for_fight(
            wcl, session, "ABC", fight, actor_map,
        )

        assert count == 1
        # Should have called session.add for the death detail
        assert session.add.call_count == 1
