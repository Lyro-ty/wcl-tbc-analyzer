"""Raid night summary generation from query results."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any


def build_raid_night_summary(
    report_code: str,
    fight_rows: list,
    player_rows: list,
    *,
    wow_data: dict | None = None,
    player_deltas: list | None = None,
) -> dict[str, Any]:
    """Build a raid night summary from raw query results.

    Args:
        report_code: WCL report code.
        fight_rows: Fight-level aggregated rows with fields: report_title,
            start_time, guild_name, encounter_name, fight_id, kill,
            duration_ms, player_count, total_deaths, total_interrupts,
            avg_parse, avg_dps.
        player_rows: Player-level rows with fields: player_name,
            encounter_name, fight_id, dps, parse_percentile, deaths,
            interrupts, kill.
        wow_data: Optional week-over-week comparison dict with keys:
            previous_report, clear_time_delta_ms, kills_delta, avg_parse_delta.
        player_deltas: Optional list of per-player parse delta rows with fields:
            player_name, encounter_name, current_parse, previous_parse,
            parse_delta.

    Returns:
        Dict matching the RaidNightSummary schema.
    """
    if not fight_rows:
        return _empty_summary(report_code)

    # Extract report metadata from first fight row
    first = fight_rows[0]
    report_title = first.report_title
    start_time = first.start_time
    guild_name = first.guild_name
    date = datetime.fromtimestamp(start_time, tz=UTC).strftime("%Y-%m-%d")

    # Separate kills and wipes
    kills = [f for f in fight_rows if f.kill]
    wipes = [f for f in fight_rows if not f.kill]

    total_bosses = len(fight_rows)
    total_kills = len(kills)
    total_wipes = len(wipes)
    total_clear_time_ms = sum(f.duration_ms for f in kills)

    # Fight highlights (kills only for speed/cleanest)
    fastest_kill = None
    slowest_kill = None
    cleanest_kill = None

    if kills:
        fastest = min(kills, key=lambda f: f.duration_ms)
        fastest_kill = {
            "encounter": fastest.encounter_name,
            "duration_ms": fastest.duration_ms,
        }
        slowest = max(kills, key=lambda f: f.duration_ms)
        slowest_kill = {
            "encounter": slowest.encounter_name,
            "duration_ms": slowest.duration_ms,
        }
        cleanest = min(kills, key=lambda f: f.total_deaths)
        cleanest_kill = {
            "encounter": cleanest.encounter_name,
            "deaths": cleanest.total_deaths,
        }

    # Most deaths boss (across all fights including wipes)
    most_deaths_boss = None
    if fight_rows:
        most_deaths_fight = max(fight_rows, key=lambda f: f.total_deaths)
        if most_deaths_fight.total_deaths > 0:
            most_deaths_boss = {
                "encounter": most_deaths_fight.encounter_name,
                "deaths": most_deaths_fight.total_deaths,
            }

    # Player highlights (kills only for DPS)
    top_dps_overall = None
    mvp_interrupts = None

    kill_fight_ids = {f.fight_id for f in kills}
    kill_players = [p for p in player_rows if p.fight_id in kill_fight_ids]

    if kill_players:
        best_dps_player = max(kill_players, key=lambda p: p.dps)
        top_dps_overall = {
            "player": best_dps_player.player_name,
            "dps": best_dps_player.dps,
            "encounter": best_dps_player.encounter_name,
        }

    # MVP interrupts across all fights
    interrupts_by_player: dict[str, int] = defaultdict(int)
    for p in player_rows:
        interrupts_by_player[p.player_name] += p.interrupts

    if interrupts_by_player:
        best_interrupter = max(
            interrupts_by_player.items(), key=lambda x: x[1],
        )
        if best_interrupter[1] > 0:
            mvp_interrupts = {
                "player": best_interrupter[0],
                "total_interrupts": best_interrupter[1],
            }

    # Most improved / biggest regression
    most_improved = None
    biggest_regression = None

    if player_deltas:
        positive = [d for d in player_deltas if d.parse_delta > 0]
        negative = [d for d in player_deltas if d.parse_delta < 0]

        if positive:
            best = max(positive, key=lambda d: d.parse_delta)
            most_improved = {
                "player": best.player_name,
                "encounter": best.encounter_name,
                "parse_delta": best.parse_delta,
            }
        if negative:
            worst = min(negative, key=lambda d: d.parse_delta)
            biggest_regression = {
                "player": worst.player_name,
                "encounter": worst.encounter_name,
                "parse_delta": worst.parse_delta,
            }

    # Week-over-week
    previous_report = None
    clear_time_delta_ms = None
    kills_delta = None
    avg_parse_delta = None

    if wow_data:
        previous_report = wow_data.get("previous_report")
        clear_time_delta_ms = wow_data.get("clear_time_delta_ms")
        kills_delta = wow_data.get("kills_delta")
        avg_parse_delta = wow_data.get("avg_parse_delta")

    return {
        "report_code": report_code,
        "report_title": report_title,
        "date": date,
        "guild_name": guild_name,
        "total_bosses": total_bosses,
        "total_kills": total_kills,
        "total_wipes": total_wipes,
        "total_clear_time_ms": total_clear_time_ms,
        "fastest_kill": fastest_kill,
        "slowest_kill": slowest_kill,
        "most_deaths_boss": most_deaths_boss,
        "cleanest_kill": cleanest_kill,
        "top_dps_overall": top_dps_overall,
        "most_improved": most_improved,
        "biggest_regression": biggest_regression,
        "mvp_interrupts": mvp_interrupts,
        "previous_report": previous_report,
        "clear_time_delta_ms": clear_time_delta_ms,
        "kills_delta": kills_delta,
        "avg_parse_delta": avg_parse_delta,
    }


def _empty_summary(report_code: str) -> dict[str, Any]:
    """Return a summary with zero values for an empty report."""
    return {
        "report_code": report_code,
        "report_title": "",
        "date": "",
        "guild_name": None,
        "total_bosses": 0,
        "total_kills": 0,
        "total_wipes": 0,
        "total_clear_time_ms": 0,
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
