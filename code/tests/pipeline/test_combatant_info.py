"""Tests for CombatantInfo parsing (consumables + gear snapshots)."""

from unittest.mock import AsyncMock, MagicMock

from shukketsu.pipeline.combatant_info import (
    ingest_combatant_info_for_report,
    parse_consumables,
    parse_gear,
)


class TestParseConsumables:
    def test_known_buffs_mapped_correctly(self):
        auras = [
            {"ability": 17628, "name": "Flask of Supreme Power"},
            {"ability": 28898, "name": "Brilliant Wizard Oil"},
            {"ability": 33254, "name": "Well Fed"},
        ]

        result = parse_consumables(auras, fight_id=1, player_name="Lyro")

        assert len(result) == 3
        # Flask
        assert result[0].category == "flask"
        assert result[0].spell_id == 17628
        assert result[0].ability_name == "Flask of Supreme Power"
        assert result[0].fight_id == 1
        assert result[0].player_name == "Lyro"
        assert result[0].active is True
        # Weapon oil
        assert result[1].category == "weapon_oil"
        assert result[1].spell_id == 28898
        assert result[1].ability_name == "Brilliant Wizard Oil"
        # Food
        assert result[2].category == "food"
        assert result[2].spell_id == 33254
        assert result[2].ability_name == "Well Fed"

    def test_unknown_buffs_ignored(self):
        auras = [
            {"ability": 99999, "name": "Some Random Buff"},
            {"ability": 12345, "name": "Another Unknown"},
        ]

        result = parse_consumables(auras, fight_id=1, player_name="Lyro")

        assert len(result) == 0

    def test_empty_auras_returns_empty(self):
        result = parse_consumables([], fight_id=1, player_name="Lyro")
        assert result == []

    def test_mixed_known_and_unknown(self):
        auras = [
            {"ability": 17626, "name": "Flask of the Titans"},
            {"ability": 99999, "name": "Unknown Buff"},
            {"ability": 11390, "name": "Elixir of the Mongoose"},
        ]

        result = parse_consumables(auras, fight_id=5, player_name="Tank")

        assert len(result) == 2
        assert result[0].category == "flask"
        assert result[0].ability_name == "Flask of the Titans"
        assert result[1].category == "elixir"
        assert result[1].ability_name == "Elixir of the Mongoose"

    def test_missing_ability_key_defaults_to_zero(self):
        """Auras missing the 'ability' key default to spell_id=0 (not in map)."""
        auras = [{"name": "Something"}]

        result = parse_consumables(auras, fight_id=1, player_name="Lyro")

        assert len(result) == 0


class TestParseGear:
    def test_basic_gear_parsing(self):
        gear = [
            {"id": 30000, "slot": 0, "itemLevel": 120},
            {"id": 30001, "slot": 1, "itemLevel": 115},
        ]

        result = parse_gear(gear, fight_id=1, player_name="Lyro")

        assert len(result) == 2
        assert result[0].slot == 0
        assert result[0].item_id == 30000
        assert result[0].item_level == 120
        assert result[0].fight_id == 1
        assert result[0].player_name == "Lyro"
        assert result[1].slot == 1
        assert result[1].item_id == 30001
        assert result[1].item_level == 115

    def test_skips_empty_slots(self):
        gear = [
            {"id": 0, "slot": 3, "itemLevel": 0},
            {"id": 30000, "slot": 4, "itemLevel": 100},
        ]

        result = parse_gear(gear, fight_id=1, player_name="Lyro")

        assert len(result) == 1
        assert result[0].item_id == 30000

    def test_missing_item_level_defaults_to_zero(self):
        gear = [
            {"id": 30000, "slot": 0},
        ]

        result = parse_gear(gear, fight_id=1, player_name="Lyro")

        assert len(result) == 1
        assert result[0].item_level == 0

    def test_empty_gear_list(self):
        result = parse_gear([], fight_id=1, player_name="Lyro")
        assert result == []

    def test_missing_slot_defaults_to_zero(self):
        gear = [
            {"id": 30000, "itemLevel": 100},
        ]

        result = parse_gear(gear, fight_id=1, player_name="Lyro")

        assert len(result) == 1
        assert result[0].slot == 0

    def test_missing_id_key_defaults_to_zero_and_skipped(self):
        """Items missing 'id' key default to 0 and are skipped."""
        gear = [{"slot": 0, "itemLevel": 100}]

        result = parse_gear(gear, fight_id=1, player_name="Lyro")

        assert len(result) == 0


class TestIngestCombatantInfoForReport:
    async def test_mocked_ingest(self):
        wcl = AsyncMock()
        session = AsyncMock()
        session.add = MagicMock()  # session.add() is sync in SQLAlchemy
        session.execute = AsyncMock()

        # Mock fight query result
        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 5
        fight.start_time = 0
        fight.end_time = 60000
        fight.report_code = "ABC123"

        fights_result = MagicMock()
        fights_result.scalars.return_value.all.return_value = [fight]

        # Mock execute to return fights on first call, then succeed on deletes
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fights_result
            return MagicMock()

        session.execute = AsyncMock(side_effect=mock_execute)

        # Mock WCL events response (CombatantInfo)
        combatant_events = [
            {
                "sourceID": 1,
                "name": "Lyro",
                "auras": [
                    {"ability": 17628, "name": "Flask of Supreme Power"},
                ],
                "gear": [
                    {"id": 30000, "slot": 0, "itemLevel": 120},
                    {"id": 30001, "slot": 1, "itemLevel": 115},
                ],
            },
        ]
        wcl.query = AsyncMock(return_value={
            "reportData": {
                "report": {
                    "events": {
                        "data": combatant_events,
                        "nextPageTimestamp": None,
                    }
                }
            }
        })

        count = await ingest_combatant_info_for_report(
            wcl, session, "ABC123",
        )

        # 1 consumable + 2 gear items = 3 rows
        assert count == 3
        assert session.add.call_count == 3
        session.flush.assert_awaited_once()

    async def test_no_fights_returns_zero(self):
        wcl = AsyncMock()
        session = AsyncMock()

        fights_result = MagicMock()
        fights_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=fights_result)

        count = await ingest_combatant_info_for_report(
            wcl, session, "NOFIGHTS",
        )

        assert count == 0

    async def test_empty_events_returns_zero(self):
        wcl = AsyncMock()
        session = AsyncMock()

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 5
        fight.start_time = 0
        fight.end_time = 60000
        fight.report_code = "EMPTY"

        fights_result = MagicMock()
        fights_result.scalars.return_value.all.return_value = [fight]

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fights_result
            return MagicMock()

        session.execute = AsyncMock(side_effect=mock_execute)

        # Empty events response
        wcl.query = AsyncMock(return_value={
            "reportData": {
                "report": {
                    "events": {
                        "data": [],
                        "nextPageTimestamp": None,
                    }
                }
            }
        })

        count = await ingest_combatant_info_for_report(
            wcl, session, "EMPTY",
        )

        assert count == 0
