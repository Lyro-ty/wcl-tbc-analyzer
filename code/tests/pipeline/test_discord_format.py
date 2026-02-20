"""Tests for Discord export formatting of raid summaries."""

from shukketsu.pipeline.discord_format import (
    format_duration,
    format_raid_summary_discord,
)


def _full_summary():
    """Return a complete summary dict with all optional fields present."""
    return {
        "report_code": "ABC123",
        "report_title": "Kara Clear",
        "date": "2024-01-15",
        "guild_name": "Test Guild",
        "total_bosses": 15,
        "total_kills": 13,
        "total_wipes": 2,
        "total_clear_time_ms": 3_600_000,
        "fastest_kill": {
            "encounter": "Gruul the Dragonkiller",
            "duration_ms": 95000,
        },
        "slowest_kill": {
            "encounter": "Netherspite",
            "duration_ms": 420000,
        },
        "most_deaths_boss": {
            "encounter": "Shade of Aran",
            "deaths": 12,
        },
        "cleanest_kill": {
            "encounter": "Noth",
            "deaths": 0,
        },
        "top_dps_overall": {
            "player": "Lyro",
            "dps": 2345.6,
            "encounter": "Gruul the Dragonkiller",
        },
        "most_improved": {
            "player": "Healer",
            "encounter": "Maiden of Virtue",
            "parse_delta": 18.5,
        },
        "biggest_regression": {
            "player": "Tank",
            "encounter": "Moroes",
            "parse_delta": -12.3,
        },
        "mvp_interrupts": {
            "player": "Lyro",
            "total_interrupts": 15,
        },
        "previous_report": "PREV01",
        "clear_time_delta_ms": -30000,
        "kills_delta": 1,
        "avg_parse_delta": 3.2,
    }


def _minimal_summary():
    """Return a summary with only required fields, all optionals None."""
    return {
        "report_code": "MIN001",
        "report_title": "Quick Raid",
        "date": "2024-02-20",
        "guild_name": None,
        "total_bosses": 3,
        "total_kills": 2,
        "total_wipes": 1,
        "total_clear_time_ms": 240000,
        "fastest_kill": None,
        "slowest_kill": None,
        "most_deaths_boss": None,
        "cleanest_kill": None,
        "top_dps_overall": None,
        "most_improved": None,
        "biggest_regression": None,
        "mvp_interrupts": None,
        "previous_report": None,
        "clear_time_delta_ms": None,
        "kills_delta": None,
        "avg_parse_delta": None,
    }


class TestFormatDuration:
    def test_exact_minutes(self):
        assert format_duration(120000) == "2m 0s"

    def test_minutes_and_seconds(self):
        assert format_duration(95000) == "1m 35s"

    def test_zero(self):
        assert format_duration(0) == "0m 0s"

    def test_sub_minute(self):
        assert format_duration(45000) == "0m 45s"

    def test_large_value(self):
        assert format_duration(3_600_000) == "60m 0s"

    def test_rounds_down_milliseconds(self):
        # 90999ms => 90s => 1m 30s (truncates, not rounds)
        assert format_duration(90999) == "1m 30s"


class TestFormatRaidSummaryDiscord:
    def test_full_summary_all_fields(self):
        summary = _full_summary()
        text = format_raid_summary_discord(summary)

        # Header
        assert "## Kara Clear" in text
        assert "2024-01-15" in text

        # Totals line
        assert "13/15 bosses" in text
        assert "Clear: 60m 0s" in text
        assert "Wipes: 2" in text

        # Highlights
        assert "Top DPS: **Lyro**" in text
        assert "2,346" in text  # 2345.6 formatted with comma, 0 decimals
        assert "Gruul the Dragonkiller" in text

        assert "Most Improved: **Healer**" in text
        assert "+19%" in text or "+18%" in text  # 18.5 rounded

        assert "Biggest Drop: **Tank**" in text
        assert "-12%" in text

        assert "Interrupt MVP: **Lyro**" in text
        assert "15 interrupts" in text

        assert "Fastest Kill: Gruul the Dragonkiller" in text
        assert "1m 35s" in text

        # Week-over-week
        assert "0m 30s faster" in text

    def test_minimal_summary_no_optional_fields(self):
        summary = _minimal_summary()
        text = format_raid_summary_discord(summary)

        # Header present
        assert "## Quick Raid" in text
        assert "2024-02-20" in text

        # Totals line
        assert "2/3 bosses" in text
        assert "Clear: 4m 0s" in text
        assert "Wipes: 1" in text

        # No highlights (all None)
        assert "Top DPS" not in text
        assert "Most Improved" not in text
        assert "Biggest Drop" not in text
        assert "Interrupt MVP" not in text
        assert "Fastest Kill" not in text
        assert "faster" not in text
        assert "slower" not in text

    def test_output_within_discord_limit(self):
        summary = _full_summary()
        text = format_raid_summary_discord(summary)
        assert len(text) <= 2000

    def test_zero_kills_zero_wipes(self):
        summary = _minimal_summary()
        summary["total_kills"] = 0
        summary["total_wipes"] = 0
        summary["total_bosses"] = 0
        summary["total_clear_time_ms"] = 0

        text = format_raid_summary_discord(summary)

        assert "0/0 bosses" in text
        assert "Clear: 0m 0s" in text
        assert "Wipes: 0" in text

    def test_slower_week_over_week(self):
        summary = _minimal_summary()
        summary["clear_time_delta_ms"] = 45000  # positive = slower

        text = format_raid_summary_discord(summary)

        assert "0m 45s slower" in text

    def test_fastest_kill_without_duration_skipped(self):
        summary = _minimal_summary()
        summary["fastest_kill"] = {"encounter": "Gruul the Dragonkiller", "duration_ms": None}

        text = format_raid_summary_discord(summary)

        assert "Fastest Kill" not in text

    def test_no_most_improved_when_none(self):
        summary = _full_summary()
        summary["most_improved"] = None

        text = format_raid_summary_discord(summary)

        assert "Most Improved" not in text
        # Other highlights should still appear
        assert "Top DPS" in text

    def test_no_biggest_regression_when_none(self):
        summary = _full_summary()
        summary["biggest_regression"] = None

        text = format_raid_summary_discord(summary)

        assert "Biggest Drop" not in text
        assert "Top DPS" in text

    def test_highlights_header_always_present(self):
        summary = _full_summary()
        text = format_raid_summary_discord(summary)
        assert "**Highlights:**" in text

    def test_all_wipes_no_kills(self):
        summary = _minimal_summary()
        summary["total_kills"] = 0
        summary["total_wipes"] = 5
        summary["total_bosses"] = 5
        summary["total_clear_time_ms"] = 0

        text = format_raid_summary_discord(summary)

        assert "0/5 bosses" in text
        assert "Wipes: 5" in text
