
from shukketsu.wcl.models import (
    Actor,
    CharacterRanking,
    EventPage,
    Fight,
    GuildReportEntry,
    RateLimitData,
    ReportRanking,
)


class TestFight:
    def test_from_camel_case(self):
        fight = Fight.model_validate(
            {"id": 1, "name": "Gruul the Dragonkiller", "startTime": 0,
             "endTime": 180000, "kill": True, "encounterID": 650,
             "difficulty": 0, "fightPercentage": 0}
        )
        assert fight.id == 1
        assert fight.name == "Gruul the Dragonkiller"
        assert fight.start_time == 0
        assert fight.end_time == 180000
        assert fight.kill is True
        assert fight.encounter_id == 650

    def test_trash_fight_has_no_encounter_id(self):
        fight = Fight.model_validate(
            {"id": 2, "name": "Trash", "startTime": 0, "endTime": 10000,
             "kill": True, "encounterID": 0, "difficulty": 0,
             "fightPercentage": 0}
        )
        assert fight.encounter_id == 0

    def test_optional_fields_default_none(self):
        fight = Fight.model_validate(
            {"id": 3, "name": "Boss", "startTime": 0, "endTime": 60000,
             "kill": False, "encounterID": 100, "difficulty": 0}
        )
        assert fight.fight_percentage is None


class TestActor:
    def test_from_camel_case(self):
        actor = Actor.model_validate(
            {"id": 1, "name": "TestRogue", "type": "Player", "subType": "Rogue",
             "server": "Faerlina"}
        )
        assert actor.id == 1
        assert actor.name == "TestRogue"
        assert actor.type == "Player"
        assert actor.sub_type == "Rogue"
        assert actor.server == "Faerlina"

    def test_npc_actor(self):
        actor = Actor.model_validate(
            {"id": 10, "name": "Gruul", "type": "NPC", "subType": "Boss"}
        )
        assert actor.type == "NPC"
        assert actor.server is None


class TestEventPage:
    def test_with_next_timestamp(self):
        page = EventPage.model_validate(
            {"data": [{"timestamp": 100}], "nextPageTimestamp": 200}
        )
        assert len(page.data) == 1
        assert page.next_page_timestamp == 200

    def test_last_page(self):
        page = EventPage.model_validate(
            {"data": [{"timestamp": 100}], "nextPageTimestamp": None}
        )
        assert page.next_page_timestamp is None

    def test_empty_data(self):
        page = EventPage.model_validate({"data": []})
        assert page.data == []
        assert page.next_page_timestamp is None


class TestRateLimitData:
    def test_parses_camel_case(self):
        rld = RateLimitData.model_validate(
            {"pointsSpentThisHour": 150, "limitPerHour": 3600,
             "pointsResetIn": 3400}
        )
        assert rld.points_spent_this_hour == 150
        assert rld.limit_per_hour == 3600
        assert rld.points_reset_in == 3400


class TestCharacterRanking:
    def test_from_camel_case(self):
        ranking = CharacterRanking.model_validate(
            {"encounterID": 650, "encounterName": "Gruul", "class": 4,
             "spec": "Combat", "percentile": 95.5, "rankPercent": 95.5,
             "duration": 180000, "amount": 1500.5, "total": 270090,
             "startTime": 1000000, "reportCode": "abc123",
             "fightID": 5, "difficulty": 0}
        )
        assert ranking.encounter_id == 650
        assert ranking.encounter_name == "Gruul"
        assert ranking.percentile == 95.5
        assert ranking.report_code == "abc123"
        assert ranking.fight_id == 5


class TestReportRanking:
    def test_from_camel_case(self):
        ranking = ReportRanking.model_validate(
            {"name": "TestRogue", "class": "Rogue", "spec": "Combat",
             "amount": 1500.5, "duration": 180000,
             "bracketPercent": 95, "rankPercent": 90,
             "best_amount": 1600.0, "total_amount": 270000}
        )
        assert ranking.name == "TestRogue"
        assert ranking.player_class == "Rogue"
        assert ranking.spec == "Combat"
        assert ranking.amount == 1500.5
        assert ranking.bracket_percent == 95


class TestGuildReportEntry:
    def test_parse_with_zone(self):
        entry = GuildReportEntry.model_validate(
            {
                "code": "abc123XYZ",
                "title": "Naxxramas - 2025-01-15",
                "startTime": 1705300000000,
                "endTime": 1705310000000,
                "zone": {"id": 2017, "name": "Naxxramas"},
            }
        )
        assert entry.code == "abc123XYZ"
        assert entry.title == "Naxxramas - 2025-01-15"
        assert entry.start_time == 1705300000000
        assert entry.end_time == 1705310000000
        assert entry.zone == {"id": 2017, "name": "Naxxramas"}

    def test_parse_without_zone(self):
        entry = GuildReportEntry.model_validate(
            {
                "code": "def456ABC",
                "title": "Weekly Raid",
                "startTime": 1705300000000,
                "endTime": 1705310000000,
                "zone": None,
            }
        )
        assert entry.code == "def456ABC"
        assert entry.zone is None

    def test_zone_defaults_to_none(self):
        entry = GuildReportEntry.model_validate(
            {
                "code": "ghi789DEF",
                "title": "Alt Run",
                "startTime": 1705300000000,
                "endTime": 1705310000000,
            }
        )
        assert entry.zone is None

    def test_parse_list_of_entries(self):
        raw_data = [
            {
                "code": "report1",
                "title": "Naxx Clear",
                "startTime": 1705300000000,
                "endTime": 1705310000000,
                "zone": {"id": 2017, "name": "Naxxramas"},
            },
            {
                "code": "report2",
                "title": "AQ40 Prog",
                "startTime": 1705200000000,
                "endTime": 1705210000000,
                "zone": {"id": 2015, "name": "Temple of Ahn'Qiraj"},
            },
        ]
        entries = [GuildReportEntry.model_validate(r) for r in raw_data]
        assert len(entries) == 2
        assert entries[0].code == "report1"
        assert entries[1].code == "report2"
        assert entries[1].zone["name"] == "Temple of Ahn'Qiraj"
