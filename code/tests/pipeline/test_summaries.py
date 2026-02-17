"""Tests for raid night summary generation."""

from datetime import UTC, datetime
from types import SimpleNamespace

from shukketsu.pipeline.summaries import build_raid_night_summary


def _fight_row(
    *,
    report_title="Naxx Clear",
    start_time=1700000000000,
    guild_name="Test Guild",
    encounter_name="Patchwerk",
    fight_id=1,
    kill=True,
    duration_ms=120000,
    player_count=25,
    total_deaths=0,
    total_interrupts=0,
    avg_parse=85.0,
    avg_dps=1500.0,
):
    return SimpleNamespace(
        report_title=report_title,
        start_time=start_time,
        guild_name=guild_name,
        encounter_name=encounter_name,
        fight_id=fight_id,
        kill=kill,
        duration_ms=duration_ms,
        player_count=player_count,
        total_deaths=total_deaths,
        total_interrupts=total_interrupts,
        avg_parse=avg_parse,
        avg_dps=avg_dps,
    )


def _player_row(
    *,
    player_name="Lyro",
    encounter_name="Patchwerk",
    fight_id=1,
    dps=2000.0,
    parse_percentile=95.0,
    deaths=0,
    interrupts=0,
    kill=True,
):
    return SimpleNamespace(
        player_name=player_name,
        encounter_name=encounter_name,
        fight_id=fight_id,
        dps=dps,
        parse_percentile=parse_percentile,
        deaths=deaths,
        interrupts=interrupts,
        kill=kill,
    )


class TestBuildRaidNightSummary:
    def test_basic_summary_with_kills_and_wipes(self):
        fight_rows = [
            _fight_row(
                encounter_name="Patchwerk", fight_id=1, kill=False,
                duration_ms=180000, total_deaths=8, avg_parse=None,
            ),
            _fight_row(
                encounter_name="Patchwerk", fight_id=2, kill=True,
                duration_ms=120000, total_deaths=2, avg_parse=85.0,
            ),
            _fight_row(
                encounter_name="Grobbulus", fight_id=3, kill=True,
                duration_ms=90000, total_deaths=0, avg_parse=90.0,
            ),
        ]
        player_rows = [
            _player_row(
                player_name="Lyro", fight_id=2, dps=2000.0,
                parse_percentile=95.0, interrupts=3,
            ),
            _player_row(
                player_name="Healer", fight_id=2, dps=200.0,
                parse_percentile=50.0, interrupts=0,
            ),
            _player_row(
                player_name="Lyro", fight_id=3, dps=1800.0,
                parse_percentile=88.0, interrupts=5,
            ),
            _player_row(
                player_name="Healer", fight_id=3, dps=150.0,
                parse_percentile=45.0, interrupts=0,
            ),
        ]

        result = build_raid_night_summary("ABC123", fight_rows, player_rows)

        assert result["report_code"] == "ABC123"
        assert result["report_title"] == "Naxx Clear"
        assert result["guild_name"] == "Test Guild"
        assert result["total_bosses"] == 3
        assert result["total_kills"] == 2
        assert result["total_wipes"] == 1
        # Clear time = sum of kill durations only
        assert result["total_clear_time_ms"] == 120000 + 90000

        # Fastest kill = Grobbulus at 90s
        assert result["fastest_kill"]["encounter"] == "Grobbulus"
        assert result["fastest_kill"]["duration_ms"] == 90000

        # Slowest kill = Patchwerk at 120s
        assert result["slowest_kill"]["encounter"] == "Patchwerk"
        assert result["slowest_kill"]["duration_ms"] == 120000

        # Most deaths boss = Patchwerk wipe (8 deaths)
        assert result["most_deaths_boss"]["encounter"] == "Patchwerk"
        assert result["most_deaths_boss"]["deaths"] == 8

        # Cleanest kill = Grobbulus (0 deaths)
        assert result["cleanest_kill"]["encounter"] == "Grobbulus"
        assert result["cleanest_kill"]["deaths"] == 0

        # Top DPS = Lyro on Patchwerk with 2000
        assert result["top_dps_overall"]["player"] == "Lyro"
        assert result["top_dps_overall"]["dps"] == 2000.0
        assert result["top_dps_overall"]["encounter"] == "Patchwerk"

        # MVP interrupts = Lyro with 3+5=8
        assert result["mvp_interrupts"]["player"] == "Lyro"
        assert result["mvp_interrupts"]["total_interrupts"] == 8

    def test_all_kills_no_wipes(self):
        fight_rows = [
            _fight_row(
                encounter_name="Patchwerk", fight_id=1, kill=True,
                duration_ms=120000, total_deaths=1,
            ),
            _fight_row(
                encounter_name="Grobbulus", fight_id=2, kill=True,
                duration_ms=90000, total_deaths=0,
            ),
            _fight_row(
                encounter_name="Gluth", fight_id=3, kill=True,
                duration_ms=150000, total_deaths=3,
            ),
        ]
        player_rows = [
            _player_row(player_name="Tank", fight_id=1, dps=800.0, interrupts=2),
            _player_row(player_name="Tank", fight_id=2, dps=750.0, interrupts=1),
            _player_row(player_name="Tank", fight_id=3, dps=900.0, interrupts=0),
        ]

        result = build_raid_night_summary("DEF456", fight_rows, player_rows)

        assert result["total_kills"] == 3
        assert result["total_wipes"] == 0
        assert result["total_clear_time_ms"] == 120000 + 90000 + 150000
        assert result["cleanest_kill"]["encounter"] == "Grobbulus"
        assert result["cleanest_kill"]["deaths"] == 0

    def test_single_fight(self):
        fight_rows = [
            _fight_row(
                encounter_name="Patchwerk", fight_id=1, kill=True,
                duration_ms=100000, total_deaths=1,
            ),
        ]
        player_rows = [
            _player_row(player_name="Lyro", fight_id=1, dps=1500.0),
        ]

        result = build_raid_night_summary("GHI789", fight_rows, player_rows)

        assert result["total_bosses"] == 1
        assert result["total_kills"] == 1
        assert result["total_wipes"] == 0
        # fastest == slowest for single kill
        assert result["fastest_kill"]["encounter"] == "Patchwerk"
        assert result["slowest_kill"]["encounter"] == "Patchwerk"

    def test_empty_report(self):
        result = build_raid_night_summary("EMPTY1", [], [])

        assert result["total_bosses"] == 0
        assert result["total_kills"] == 0
        assert result["total_wipes"] == 0
        assert result["total_clear_time_ms"] == 0
        assert result["fastest_kill"] is None
        assert result["slowest_kill"] is None
        assert result["most_deaths_boss"] is None
        assert result["cleanest_kill"] is None
        assert result["top_dps_overall"] is None
        assert result["mvp_interrupts"] is None
        assert result["previous_report"] is None

    def test_week_over_week_comparison(self):
        fight_rows = [
            _fight_row(
                encounter_name="Patchwerk", fight_id=1, kill=True,
                duration_ms=100000,
            ),
        ]
        player_rows = [
            _player_row(player_name="Lyro", fight_id=1, dps=1500.0),
        ]
        wow_data = {
            "previous_report": "PREV01",
            "clear_time_delta_ms": -15000,
            "kills_delta": 2,
            "avg_parse_delta": 5.3,
        }

        result = build_raid_night_summary(
            "CUR001", fight_rows, player_rows, wow_data=wow_data,
        )

        assert result["previous_report"] == "PREV01"
        assert result["clear_time_delta_ms"] == -15000
        assert result["kills_delta"] == 2
        assert result["avg_parse_delta"] == 5.3

    def test_no_week_over_week_defaults_to_none(self):
        fight_rows = [
            _fight_row(encounter_name="Patchwerk", fight_id=1, kill=True),
        ]
        player_rows = [
            _player_row(player_name="Lyro", fight_id=1),
        ]

        result = build_raid_night_summary("ABC123", fight_rows, player_rows)

        assert result["previous_report"] is None
        assert result["clear_time_delta_ms"] is None
        assert result["kills_delta"] is None
        assert result["avg_parse_delta"] is None

    def test_most_improved_and_biggest_regression(self):
        fight_rows = [
            _fight_row(encounter_name="Patchwerk", fight_id=1, kill=True),
        ]
        player_rows = [
            _player_row(
                player_name="Improved", fight_id=1, parse_percentile=90.0,
            ),
            _player_row(
                player_name="Regressed", fight_id=1, parse_percentile=40.0,
            ),
        ]
        # Parse deltas from previous report
        player_deltas = [
            SimpleNamespace(
                player_name="Improved", encounter_name="Patchwerk",
                current_parse=90.0, previous_parse=70.0, parse_delta=20.0,
            ),
            SimpleNamespace(
                player_name="Regressed", encounter_name="Patchwerk",
                current_parse=40.0, previous_parse=75.0, parse_delta=-35.0,
            ),
        ]

        result = build_raid_night_summary(
            "ABC123", fight_rows, player_rows, player_deltas=player_deltas,
        )

        assert result["most_improved"]["player"] == "Improved"
        assert result["most_improved"]["parse_delta"] == 20.0
        assert result["biggest_regression"]["player"] == "Regressed"
        assert result["biggest_regression"]["parse_delta"] == -35.0

    def test_no_player_deltas_means_no_improved_or_regressed(self):
        fight_rows = [
            _fight_row(encounter_name="Patchwerk", fight_id=1, kill=True),
        ]
        player_rows = [
            _player_row(player_name="Lyro", fight_id=1),
        ]

        result = build_raid_night_summary("ABC123", fight_rows, player_rows)

        assert result["most_improved"] is None
        assert result["biggest_regression"] is None

    def test_all_wipes_no_kills(self):
        fight_rows = [
            _fight_row(
                encounter_name="Patchwerk", fight_id=1, kill=False,
                duration_ms=180000, total_deaths=15,
            ),
            _fight_row(
                encounter_name="Patchwerk", fight_id=2, kill=False,
                duration_ms=160000, total_deaths=12,
            ),
        ]
        player_rows = [
            _player_row(
                player_name="Lyro", fight_id=1, dps=1500.0, kill=False,
            ),
            _player_row(
                player_name="Lyro", fight_id=2, dps=1600.0, kill=False,
            ),
        ]

        result = build_raid_night_summary("WIPES1", fight_rows, player_rows)

        assert result["total_kills"] == 0
        assert result["total_wipes"] == 2
        assert result["total_clear_time_ms"] == 0
        assert result["fastest_kill"] is None
        assert result["slowest_kill"] is None
        assert result["cleanest_kill"] is None
        # Most deaths boss still works for wipes
        assert result["most_deaths_boss"]["encounter"] == "Patchwerk"
        assert result["most_deaths_boss"]["deaths"] == 15
        # Top DPS still reported from kills only (None if no kills)
        assert result["top_dps_overall"] is None

    def test_no_interrupts_means_none_mvp(self):
        fight_rows = [
            _fight_row(encounter_name="Patchwerk", fight_id=1, kill=True),
        ]
        player_rows = [
            _player_row(
                player_name="Lyro", fight_id=1, dps=2000.0, interrupts=0,
            ),
            _player_row(
                player_name="Healer", fight_id=1, dps=200.0, interrupts=0,
            ),
        ]

        result = build_raid_night_summary("ABC123", fight_rows, player_rows)

        assert result["mvp_interrupts"] is None

    def test_date_formatted_from_start_time(self):
        # start_time 1700000000 = 2023-11-14
        fight_rows = [
            _fight_row(
                encounter_name="Patchwerk", fight_id=1, kill=True,
                start_time=1700000000000,
            ),
        ]
        player_rows = [
            _player_row(player_name="Lyro", fight_id=1),
        ]

        result = build_raid_night_summary("ABC123", fight_rows, player_rows)

        # Date should be derived from start_time (epoch milliseconds)
        expected_date = datetime.fromtimestamp(
            1700000000000 / 1000, tz=UTC,
        ).strftime("%Y-%m-%d")
        assert result["date"] == expected_date
