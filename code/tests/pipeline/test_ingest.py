from unittest.mock import AsyncMock, MagicMock

import pytest

from shukketsu.pipeline.ingest import (
    ingest_report,
    parse_fights,
    parse_rankings_to_performances,
    parse_report,
)
from shukketsu.pipeline.normalize import compute_dps, compute_hps, is_boss_fight


class TestNormalize:
    def test_compute_dps(self):
        # 270000 damage over 180000ms (180s) = 1500.0 DPS
        assert compute_dps(270000, 180000) == pytest.approx(1500.0)

    def test_compute_dps_fractional(self):
        assert compute_dps(100000, 60000) == pytest.approx(1666.6666666666667)

    def test_compute_dps_zero_duration(self):
        assert compute_dps(100000, 0) == 0.0

    def test_compute_hps(self):
        assert compute_hps(540000, 180000) == pytest.approx(3000.0)

    def test_compute_hps_zero_duration(self):
        assert compute_hps(100000, 0) == 0.0

    def test_is_boss_fight_true(self):
        assert is_boss_fight({"encounterID": 650}) is True

    def test_is_boss_fight_false_zero(self):
        assert is_boss_fight({"encounterID": 0}) is False

    def test_is_boss_fight_false_missing(self):
        assert is_boss_fight({}) is False


class TestParseReport:
    def test_basic_report(self):
        data = {
            "title": "Gruul's Lair - Feb 15",
            "startTime": 1700000000000,
            "endTime": 1700003600000,
            "guild": {"id": 12345, "name": "Test Guild"},
        }
        report = parse_report(data, "abc123")
        assert report.code == "abc123"
        assert report.title == "Gruul's Lair - Feb 15"
        assert report.guild_name == "Test Guild"
        assert report.guild_id == 12345
        assert report.start_time == 1700000000000
        assert report.end_time == 1700003600000

    def test_report_no_guild(self):
        data = {
            "title": "PUG Run",
            "startTime": 1700000000000,
            "endTime": 1700003600000,
            "guild": None,
        }
        report = parse_report(data, "xyz789")
        assert report.guild_name is None
        assert report.guild_id is None


class TestParseFights:
    FIGHTS_DATA = [
        {
            "id": 1, "name": "Trash", "startTime": 0, "endTime": 30000,
            "kill": True, "encounterID": 0, "difficulty": 0, "fightPercentage": 0,
        },
        {
            "id": 2, "name": "High King Maulgar", "startTime": 30000, "endTime": 180000,
            "kill": True, "encounterID": 649, "difficulty": 0, "fightPercentage": 0,
        },
        {
            "id": 3, "name": "Gruul the Dragonkiller", "startTime": 200000, "endTime": 380000,
            "kill": False, "encounterID": 650, "difficulty": 0, "fightPercentage": 35,
        },
    ]

    def test_skips_trash(self):
        fights = parse_fights(self.FIGHTS_DATA, "abc123")
        names = [f.encounter_id for f in fights]
        assert 0 not in names

    def test_parses_boss_fights(self):
        fights = parse_fights(self.FIGHTS_DATA, "abc123")
        assert len(fights) == 2

    def test_sets_fields(self):
        fights = parse_fights(self.FIGHTS_DATA, "abc123")
        gruul = [f for f in fights if f.encounter_id == 650][0]
        assert gruul.report_code == "abc123"
        assert gruul.fight_id == 3
        assert gruul.start_time == 200000
        assert gruul.end_time == 380000
        assert gruul.kill is False
        assert gruul.difficulty == 0


class TestParseRankingsToPerformances:
    RANKING_DATA = [
        {
            "name": "TestRogue",
            "class": "Rogue",
            "spec": "Combat",
            "amount": 1500.5,
            "duration": 180000,
            "bracketPercent": 95,
            "rankPercent": 90,
            "server": {"name": "Faerlina"},
            "total": 270090,
            "deaths": 0,
            "itemLevel": 141,
        },
        {
            "name": "TestMage",
            "class": "Mage",
            "spec": "Fire",
            "amount": 1200.0,
            "duration": 180000,
            "bracketPercent": 75,
            "rankPercent": 70,
            "server": {"name": "Faerlina"},
            "total": 216000,
            "deaths": 1,
            "itemLevel": 138,
        },
    ]

    def test_parses_all_players(self):
        perfs = parse_rankings_to_performances(self.RANKING_DATA, 42, set())
        assert len(perfs) == 2

    def test_sets_player_fields(self):
        perfs = parse_rankings_to_performances(self.RANKING_DATA, 42, set())
        rogue = [p for p in perfs if p.player_name == "TestRogue"][0]
        assert rogue.fight_id == 42
        assert rogue.player_class == "Rogue"
        assert rogue.player_spec == "Combat"
        assert rogue.player_server == "Faerlina"
        assert rogue.dps == pytest.approx(1500.5)
        assert rogue.total_damage == 270090
        assert rogue.parse_percentile == 90
        assert rogue.ilvl_parse_percentile == 95
        assert rogue.deaths == 0
        assert rogue.item_level == 141

    def test_identifies_my_character(self):
        my_names = {"TestRogue"}
        perfs = parse_rankings_to_performances(self.RANKING_DATA, 42, my_names)
        rogue = [p for p in perfs if p.player_name == "TestRogue"][0]
        mage = [p for p in perfs if p.player_name == "TestMage"][0]
        assert rogue.is_my_character is True
        assert mage.is_my_character is False

    def test_no_my_characters(self):
        perfs = parse_rankings_to_performances(self.RANKING_DATA, 42, set())
        assert all(not p.is_my_character for p in perfs)


class TestReingestionIdempotency:
    """Verify that calling ingest_report twice with the same report doesn't raise."""

    REPORT_DATA = {
        "reportData": {
            "report": {
                "title": "Naxx Clear",
                "startTime": 1700000000000,
                "endTime": 1700003600000,
                "guild": {"id": 1, "name": "Test"},
                "fights": [
                    {
                        "id": 1, "name": "Patchwerk", "startTime": 0, "endTime": 180000,
                        "kill": True, "encounterID": 201115, "difficulty": 0,
                    },
                ],
                "rankings": {"data": []},
            }
        }
    }

    async def test_merge_report_called(self):
        """Verify ingest uses session.merge for report (not add)."""
        mock_wcl = AsyncMock()
        mock_wcl.query.return_value = self.REPORT_DATA

        mock_session = AsyncMock()
        # select returns empty (no existing fights)
        mock_select_result = MagicMock()
        mock_select_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_select_result
        mock_session.flush = AsyncMock()

        await ingest_report(mock_wcl, mock_session, "abc123")

        # session.merge should have been called (for report + encounter)
        assert mock_session.merge.await_count >= 1

    async def test_deletes_existing_before_reingest(self):
        """Verify that existing fights are deleted before re-inserting."""
        mock_wcl = AsyncMock()
        mock_wcl.query.return_value = self.REPORT_DATA

        mock_session = AsyncMock()
        # First execute returns existing fight IDs
        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(return_value=iter([(42,)]))

        # Subsequent executes return empty results
        empty_result = MagicMock()
        empty_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.execute.side_effect = [existing_result, None, None, empty_result]
        mock_session.flush = AsyncMock()

        await ingest_report(mock_wcl, mock_session, "abc123")

        # select existing + delete perfs + delete fights + select rankings
        assert mock_session.execute.await_count >= 3
