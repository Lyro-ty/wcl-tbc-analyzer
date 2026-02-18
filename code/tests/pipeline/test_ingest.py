from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shukketsu.pipeline.ingest import (
    IngestResult,
    ingest_report,
    parse_fights,
    parse_rankings_to_performances,
    parse_report,
)
from shukketsu.pipeline.normalize import is_boss_fight


class TestNormalize:
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

    def test_fight_percentage_stored_for_wipe(self):
        """Verify fightPercentage from WCL data appears in parsed Fight object."""
        fights = parse_fights(self.FIGHTS_DATA, "abc123")
        gruul = [f for f in fights if f.encounter_id == 650][0]
        assert gruul.fight_percentage == 35

    def test_fight_percentage_stored_for_kill(self):
        """Verify fightPercentage=0 is stored for kills."""
        fights = parse_fights(self.FIGHTS_DATA, "abc123")
        maulgar = [f for f in fights if f.encounter_id == 649][0]
        assert maulgar.fight_percentage == 0

    def test_fight_percentage_none_when_missing(self):
        """Verify fight_percentage defaults to None when not present in WCL data."""
        fights_data = [
            {
                "id": 5, "name": "Patchwerk", "startTime": 0, "endTime": 180000,
                "kill": True, "encounterID": 201115, "difficulty": 0,
            },
        ]
        fights = parse_fights(fights_data, "abc123")
        assert len(fights) == 1
        assert fights[0].fight_percentage is None


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
        mock_session.add = MagicMock()  # session.add() is sync in SQLAlchemy
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
        mock_session.add = MagicMock()  # session.add() is sync in SQLAlchemy
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


class TestIngestResultSnapshots:
    """Verify IngestResult includes snapshots field."""

    def test_ingest_result_has_snapshots_field(self):
        result = IngestResult(fights=5, performances=25, snapshots=3)
        assert result.snapshots == 3

    def test_ingest_result_snapshots_default_zero(self):
        result = IngestResult(fights=5, performances=25)
        assert result.snapshots == 0


class TestSnapshotsRemovedFromIngest:
    """Verify ingest_report no longer calls snapshot_all_characters.

    Snapshots are now the caller's responsibility (pull_my_logs, auto_ingest).
    """

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

    async def test_ingest_report_does_not_call_snapshots(self):
        """Verify ingest_report no longer imports or calls snapshot_all_characters."""
        mock_wcl = AsyncMock()
        mock_wcl.query.return_value = self.REPORT_DATA

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # session.add() is sync in SQLAlchemy
        mock_select_result = MagicMock()
        mock_select_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_select_result
        mock_session.flush = AsyncMock()

        result = await ingest_report(mock_wcl, mock_session, "abc123")

        # snapshots field defaults to 0 since ingest_report no longer runs them
        assert result.snapshots == 0
        assert result.fights == 1
        assert result.enrichment_errors == []

    async def test_enrichment_errors_returned(self):
        """Verify enrichment_errors field is populated when enrichment fails."""
        result = IngestResult(
            fights=5, performances=25,
            enrichment_errors=["combatant_info", "death_events_fight_1"],
        )
        assert len(result.enrichment_errors) == 2
        assert "combatant_info" in result.enrichment_errors


class TestIngestEventsWiring:
    """Verify ingest_report calls event pipelines when ingest_events=True."""

    REPORT_DATA = {
        "reportData": {
            "report": {
                "title": "Naxx Clear",
                "startTime": 1700000000000,
                "endTime": 1700003600000,
                "guild": {"id": 1, "name": "Test"},
                "masterData": {
                    "actors": [
                        {
                            "id": 5, "name": "TestWarrior",
                            "type": "Warrior", "subType": "Arms",
                        },
                        {
                            "id": 6, "name": "TestMage",
                            "type": "Mage", "subType": "Fire",
                        },
                    ]
                },
                "fights": [
                    {
                        "id": 1, "name": "Patchwerk",
                        "startTime": 0, "endTime": 180000,
                        "kill": True, "encounterID": 201115, "difficulty": 0,
                    },
                ],
                "rankings": {"data": []},
            }
        }
    }

    def _make_mocks(self):
        """Create standard mock WCL client and DB session."""
        mock_wcl = AsyncMock()
        mock_wcl.query.return_value = self.REPORT_DATA

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # session.add() is sync in SQLAlchemy
        mock_select_result = MagicMock()
        mock_select_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_select_result
        mock_session.flush = AsyncMock()

        return mock_wcl, mock_session

    @patch(
        "shukketsu.pipeline.resource_events.ingest_resource_data_for_fight",
        new_callable=AsyncMock, return_value=3,
    )
    @patch(
        "shukketsu.pipeline.cast_events.ingest_cast_events_for_fight",
        new_callable=AsyncMock, return_value=10,
    )
    @patch(
        "shukketsu.pipeline.death_events.ingest_death_events_for_fight",
        new_callable=AsyncMock, return_value=2,
    )
    @patch(
        "shukketsu.pipeline.combatant_info.ingest_combatant_info_for_report",
        new_callable=AsyncMock, return_value=5,
    )
    async def test_ingest_events_calls_all_pipelines(
        self, mock_combatant, mock_death, mock_cast, mock_resource,
    ):
        """All 4 event pipelines are called when ingest_events=True."""
        mock_wcl, mock_session = self._make_mocks()

        result = await ingest_report(
            mock_wcl, mock_session, "abc123", ingest_events=True,
        )

        mock_combatant.assert_awaited_once_with(
            mock_wcl, mock_session, "abc123",
        )
        mock_death.assert_awaited_once()
        mock_cast.assert_awaited_once()
        mock_resource.assert_awaited_once()

        # 5 (combatant) + 2 (death) + 10 (cast) + 3 (resource) = 20
        assert result.event_rows == 20

    @patch(
        "shukketsu.pipeline.resource_events.ingest_resource_data_for_fight",
        new_callable=AsyncMock, return_value=3,
    )
    @patch(
        "shukketsu.pipeline.cast_events.ingest_cast_events_for_fight",
        new_callable=AsyncMock, return_value=10,
    )
    @patch(
        "shukketsu.pipeline.death_events.ingest_death_events_for_fight",
        new_callable=AsyncMock, return_value=2,
    )
    @patch(
        "shukketsu.pipeline.combatant_info.ingest_combatant_info_for_report",
        new_callable=AsyncMock, return_value=5,
    )
    async def test_ingest_events_builds_actor_maps(
        self, mock_combatant, mock_death, mock_cast, mock_resource,
    ):
        """Actor maps are built from masterData and passed to pipelines."""
        mock_wcl, mock_session = self._make_mocks()

        await ingest_report(
            mock_wcl, mock_session, "abc123", ingest_events=True,
        )

        # Verify cast_events received correct actor_name_by_id and player_class_map
        cast_call = mock_cast.call_args
        actor_name_by_id = cast_call[0][4]  # 5th positional arg
        player_class_map = cast_call[0][5]  # 6th positional arg

        assert actor_name_by_id == {5: "TestWarrior", 6: "TestMage"}
        assert player_class_map == {
            "TestWarrior": "Warrior", "TestMage": "Mage",
        }

        # Verify resource_events received correct actor_name_by_id
        resource_call = mock_resource.call_args
        resource_actors = resource_call[0][4]  # 5th positional arg
        assert resource_actors == {5: "TestWarrior", 6: "TestMage"}

    async def test_ingest_events_false_skips_pipelines(self):
        """No event pipelines are called when ingest_events=False."""
        mock_wcl, mock_session = self._make_mocks()

        with (
            patch(
                "shukketsu.pipeline.combatant_info.ingest_combatant_info_for_report",
                new_callable=AsyncMock,
            ) as mock_combatant,
            patch(
                "shukketsu.pipeline.death_events.ingest_death_events_for_fight",
                new_callable=AsyncMock,
            ) as mock_death,
            patch(
                "shukketsu.pipeline.cast_events.ingest_cast_events_for_fight",
                new_callable=AsyncMock,
            ) as mock_cast,
            patch(
                "shukketsu.pipeline.resource_events.ingest_resource_data_for_fight",
                new_callable=AsyncMock,
            ) as mock_resource,
        ):
            result = await ingest_report(
                mock_wcl, mock_session, "abc123", ingest_events=False,
            )

            mock_combatant.assert_not_awaited()
            mock_death.assert_not_awaited()
            mock_cast.assert_not_awaited()
            mock_resource.assert_not_awaited()

            assert result.event_rows == 0
