"""Player and encounter-level agent tools (11 tools)."""

from shukketsu.agent.tool_utils import _format_duration, db_tool, wildcard
from shukketsu.db import queries as q
from shukketsu.pipeline.constants import ROLE_BY_SPEC


def _metric_label(spec: str | None) -> tuple[str, str]:
    """Return (label, field) for the primary metric based on spec role.

    Healers get ("HPS", "hps"); everyone else gets ("DPS", "dps").
    Defaults to DPS when spec is None or unknown.
    """
    if spec and ROLE_BY_SPEC.get(spec) == "healer":
        return "HPS", "hps"
    return "DPS", "dps"


@db_tool
async def get_my_performance(
    session,
    encounter_name: str,
    player_name: str,
    bests_only: bool = False,
) -> str:
    """Get a player's recent performance data for a specific encounter.
    Returns DPS, parse percentile, deaths, and other metrics.
    Set bests_only=True to get personal records (best DPS/parse/HPS) instead."""
    if bests_only:
        if encounter_name and encounter_name.strip():
            result = await session.execute(
                q.PERSONAL_BESTS_BY_ENCOUNTER,
                {"player_name": wildcard(player_name),
                 "encounter_name": wildcard(encounter_name)},
            )
        else:
            result = await session.execute(
                q.PERSONAL_BESTS,
                {"player_name": wildcard(player_name)},
            )
        rows = result.fetchall()
        if not rows:
            return f"No personal bests found for '{player_name}'."
        lines = [f"Personal bests for {player_name}:\n"]
        for r in rows:
            parse_str = (
                f"{r.best_parse}%" if r.best_parse is not None else "N/A"
            )
            ilvl_str = (
                f"{r.peak_ilvl}" if r.peak_ilvl is not None else "N/A"
            )
            lines.append(
                f"{r.encounter_name}: Best DPS {r.best_dps:,.1f} | "
                f"Best Parse {parse_str} | Best HPS {r.best_hps:,.1f} | "
                f"Kills: {r.kill_count} | Peak iLvl: {ilvl_str}"
            )
        return "\n".join(lines)

    result = await session.execute(
        q.MY_PERFORMANCE,
        {"encounter_name": wildcard(encounter_name),
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No performance data found for '{player_name}' "
            f"on '{encounter_name}'."
        )

    lines = [f"Performance for {player_name} on {encounter_name}:\n"]
    for r in rows:
        outcome = "Kill" if r.kill else "Wipe"
        label, _ = _metric_label(r.player_spec)
        val = r.hps if label == "HPS" else r.dps
        lines.append(
            f"- {r.player_spec} {r.player_class} | "
            f"{label}: {val:,.1f} | "
            f"Parse: {r.parse_percentile}% "
            f"(iLvl: {r.ilvl_parse_percentile}%) | "
            f"Deaths: {r.deaths} | iLvl: {r.item_level} | "
            f"{outcome} in {_format_duration(r.duration_ms)}"
        )
    return "\n".join(lines)


@db_tool
async def get_top_rankings(
    session, encounter_name: str, class_name: str, spec_name: str,
) -> str:
    """Get top player rankings for a specific encounter, class, and spec.
    Returns the top 10 players with their DPS, guild, and item level."""
    result = await session.execute(
        q.TOP_RANKINGS,
        {"encounter_name": wildcard(encounter_name),
         "class_name": wildcard(class_name),
         "spec_name": wildcard(spec_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No top rankings found for {spec_name} {class_name} "
            f"on {encounter_name}."
        )

    label, _ = _metric_label(spec_name)
    lines = [f"Top {spec_name} {class_name} rankings on {encounter_name}:\n"]
    for r in rows:
        lines.append(
            f"#{r.rank_position} {r.player_name} ({r.player_server}) | "
            f"{label}: {r.amount:,.1f} | iLvl: {r.item_level} | "
            f"Duration: {_format_duration(r.duration_ms)} | "
            f"Guild: {r.guild_name}"
        )
    return "\n".join(lines)


@db_tool
async def compare_to_top(
    session,
    encounter_name: str,
    player_name: str,
    class_name: str,
    spec_name: str,
) -> str:
    """Compare a player's performance to top rankings for the same class/spec.
    Shows side-by-side metrics for the player vs top 10 average."""
    result = await session.execute(
        q.COMPARE_TO_TOP,
        {"encounter_name": wildcard(encounter_name),
         "player_name": wildcard(player_name),
         "class_name": wildcard(class_name),
         "spec_name": wildcard(spec_name)},
    )
    row = result.fetchone()
    if not row or row.dps is None:
        return (
            f"No comparison data found for {player_name} "
            f"on {encounter_name}."
        )

    label, _ = _metric_label(row.player_spec)
    my_val = row.hps if label == "HPS" else row.dps
    # top_rankings.amount stores the primary metric (HPS for healers,
    # DPS for others), so avg_dps/min_dps/max_dps contain the correct
    # values regardless of role.
    gap = (
        (row.avg_dps - my_val) / row.avg_dps * 100
    ) if row.avg_dps else 0
    return (
        f"Comparison for {player_name} ({row.player_spec} "
        f"{row.player_class}) on {encounter_name}:\n"
        f"  Your {label}: {my_val:,.1f} | Parse: {row.parse_percentile}%\n"
        f"  Top 10 avg {label}: {row.avg_dps:,.1f} "
        f"(range: {row.min_dps:,.1f} - {row.max_dps:,.1f})\n"
        f"  Gap to top avg: {gap:.1f}%\n"
        f"  Your iLvl: {row.item_level} | "
        f"Top avg iLvl: {row.avg_ilvl:.0f}\n"
        f"  Your deaths: {row.deaths}"
    )


@db_tool
async def get_fight_details(
    session, report_code: str, fight_id: int,
) -> str:
    """Get detailed breakdown of all player performances in a specific fight.
    Shows every player's DPS, parse, deaths, and utility metrics."""
    result = await session.execute(
        q.FIGHT_DETAILS,
        {"report_code": report_code, "fight_id": fight_id},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No data found for fight {fight_id} in report {report_code}."
        )

    first = rows[0]
    outcome = "Kill" if first.kill else "Wipe"
    lines = [
        f"Fight: {first.encounter_name} ({outcome}, "
        f"{_format_duration(first.duration_ms)}) — {first.report_title}\n"
    ]
    for r in rows:
        label, _ = _metric_label(r.player_spec)
        val = r.hps if label == "HPS" else r.dps
        lines.append(
            f"  {r.player_name} ({r.player_spec} {r.player_class}) | "
            f"{label}: {val:,.1f} | Parse: {r.parse_percentile}% | "
            f"Deaths: {r.deaths} | Int: {r.interrupts} | "
            f"Disp: {r.dispels}"
        )
    return "\n".join(lines)


@db_tool
async def get_progression(
    session, character_name: str, encounter_name: str,
) -> str:
    """Get time-series progression data for a character on an encounter.
    Shows best/median parse and DPS over time."""
    result = await session.execute(
        q.PROGRESSION,
        {"character_name": wildcard(character_name),
         "encounter_name": wildcard(encounter_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No progression data found for {character_name} "
            f"on {encounter_name}."
        )

    lines = [
        f"Progression for {rows[0].character_name} "
        f"on {rows[0].encounter_name}:\n"
    ]
    for r in rows:
        lines.append(
            f"  {r.time.strftime('%Y-%m-%d')} | "
            f"Best Parse: {r.best_parse}% | "
            f"Median: {r.median_parse}% | Best DPS: {r.best_dps:,.1f} | "
            f"Kills: {r.kill_count} | Avg Deaths: {r.avg_deaths:.1f}"
        )
    return "\n".join(lines)


@db_tool
async def get_deaths_and_mechanics(
    session, encounter_name: str,
) -> str:
    """Get death and mechanic failure analysis for an encounter.
    Shows who died, how often, and their interrupt/dispel contributions."""
    result = await session.execute(
        q.DEATHS_AND_MECHANICS,
        {"encounter_name": wildcard(encounter_name)},
    )
    rows = result.fetchall()
    if not rows:
        return f"No death/mechanic data found for {encounter_name}."

    lines = [f"Deaths and mechanics on {encounter_name}:\n"]
    for r in rows:
        outcome = "Kill" if r.kill else "Wipe"
        lines.append(
            f"  {r.player_name} ({r.player_spec} {r.player_class}) | "
            f"Deaths: {r.deaths} | Int: {r.interrupts} | "
            f"Disp: {r.dispels} | "
            f"{outcome} ({_format_duration(r.duration_ms)})"
        )
    return "\n".join(lines)


@db_tool
async def search_fights(session, encounter_name: str) -> str:
    """Search for recent fights by encounter name.
    Returns matching fights across all reports, newest first."""
    result = await session.execute(
        q.SEARCH_FIGHTS,
        {"encounter_name": wildcard(encounter_name)},
    )
    rows = result.fetchall()
    if not rows:
        return f"No fights found matching '{encounter_name}'."

    lines = [f"Fights matching '{encounter_name}':\n"]
    for r in rows:
        outcome = "Kill" if r.kill else "Wipe"
        lines.append(
            f"  {r.report_code}#{r.fight_id} {r.encounter_name} | "
            f"{outcome} | {_format_duration(r.duration_ms)} | "
            f"{r.report_title}"
        )
    return "\n".join(lines)


@db_tool
async def get_spec_leaderboard(session, encounter_name: str) -> str:
    """Get a leaderboard of all class/spec combinations ranked by average DPS
    on an encounter. Shows avg DPS, max DPS, median DPS, avg parse percentile,
    and sample size for each spec."""
    result = await session.execute(
        q.SPEC_LEADERBOARD,
        {"encounter_name": wildcard(encounter_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No spec performance data found for '{encounter_name}'."
        )

    lines = [
        f"Spec performance leaderboard on {encounter_name} (kills only):\n"
    ]
    for i, r in enumerate(rows, 1):
        label, _ = _metric_label(r.player_spec)
        if label == "HPS":
            avg_val = getattr(r, "avg_hps", 0.0) or 0.0
            max_val = getattr(r, "max_hps", 0.0) or 0.0
            med_val = getattr(r, "median_hps", 0.0) or 0.0
        else:
            avg_val = r.avg_dps
            max_val = r.max_dps
            med_val = r.median_dps
        lines.append(
            f"#{i} {r.player_spec} {r.player_class} | "
            f"Avg {label}: {avg_val:,.1f} | Max: {max_val:,.1f} | "
            f"Median: {med_val:,.1f} | Avg Parse: {r.avg_parse}% | "
            f"iLvl: {r.avg_ilvl} | n={r.sample_size}"
        )
    return "\n".join(lines)


@db_tool
async def resolve_my_fights(
    session, encounter_name: str | None = None, count: int = 5,
) -> str:
    """Find your recent fights. Returns report codes and fight IDs for your
    tracked character's recent kills. Use this to look up fight details
    without needing to know report codes.
    If encounter_name is provided, filters to that boss.
    Returns up to 'count' recent fights (default 5)."""
    count = min(max(count, 1), 25)
    result = await session.execute(
        q.MY_RECENT_KILLS,
        {
            "encounter_name": (
                wildcard(encounter_name) if encounter_name else None
            ),
            "limit": count,
        },
    )
    rows = result.fetchall()
    if not rows:
        filter_msg = f" on '{encounter_name}'" if encounter_name else ""
        return (
            f"No recent kills found for your tracked "
            f"characters{filter_msg}."
        )

    lines = ["Your recent kills:\n"]
    for i, r in enumerate(rows, 1):
        duration = _format_duration(r.duration_ms)
        parse_str = (
            f"{r.parse_percentile}%"
            if r.parse_percentile is not None else "N/A"
        )
        lines.append(
            f"  {i}. {r.encounter_name} — report {r.report_code} fight "
            f"#{r.fight_id} | DPS: {r.dps:,.1f} | Parse: {parse_str} | "
            f"{duration}"
        )
    return "\n".join(lines)


@db_tool
async def get_wipe_progression(
    session, report_code: str, encounter_name: str,
) -> str:
    """Show wipe-to-kill progression for a boss encounter in a raid.
    Lists each attempt with boss HP% at wipe, DPS, deaths, and duration.
    Useful for seeing how quickly the raid learned the fight."""
    result = await session.execute(
        q.WIPE_PROGRESSION,
        {"report_code": report_code,
         "encounter_name": wildcard(encounter_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No attempts found for '{encounter_name}' "
            f"in report {report_code}."
        )

    lines = [f"{encounter_name} Progression (report {report_code}):"]
    for i, r in enumerate(rows, 1):
        duration = _format_duration(r.duration_ms)
        if r.kill:
            parse_str = (
                f" | Parse: {r.avg_parse}%"
                if r.avg_parse is not None else ""
            )
            lines.append(
                f"  Attempt {i}: KILL | {duration} | "
                f"Avg DPS: {r.avg_dps:,.1f} | "
                f"Deaths: {r.total_deaths} | "
                f"{r.player_count} players{parse_str}"
            )
        else:
            pct = (
                r.fight_percentage
                if r.fight_percentage is not None else 0
            )
            lines.append(
                f"  Attempt {i}: WIPE at {pct:.1f}% | {duration} | "
                f"Avg DPS: {r.avg_dps:,.1f} | "
                f"Deaths: {r.total_deaths} | "
                f"{r.player_count} players"
            )
    return "\n".join(lines)


@db_tool
async def get_regressions(
    session, player_name: str | None = None,
) -> str:
    """Check for performance regressions or improvements on farm bosses.
    Compares recent kills (last 2) against rolling baseline (kills 3-7).
    Flags significant drops (>=15 percentile points) as regressions.
    Only tracks registered characters."""
    result = await session.execute(
        q.REGRESSION_CHECK,
        {"player_name": wildcard(player_name) if player_name else None},
    )
    rows = result.fetchall()
    if not rows:
        return (
            "No significant performance changes detected. "
            "All tracked characters are performing within normal range "
            "on farm bosses (requires at least 7 kills per boss)."
        )

    lines = ["Performance Changes Detected:\n"]
    for r in rows:
        if r.parse_delta < 0:
            direction = "REGRESSION"
            delta_str = f"down {abs(r.parse_delta)} pts"
        else:
            direction = "IMPROVEMENT"
            delta_str = f"up {r.parse_delta} pts"

        dps_str = f"{r.recent_dps:,.1f}"
        baseline_dps_str = f"{r.baseline_dps:,.1f}"
        dps_delta = (
            f"{r.dps_delta_pct:+.1f}%"
            if r.dps_delta_pct is not None
            else "N/A"
        )

        lines.append(
            f"  [{direction}] {r.player_name} on {r.encounter_name}: "
            f"Parse {r.recent_parse}% (was {r.baseline_parse}%) "
            f"-- {delta_str} | "
            f"DPS: {dps_str} (was {baseline_dps_str}, {dps_delta})"
        )
    return "\n".join(lines)
