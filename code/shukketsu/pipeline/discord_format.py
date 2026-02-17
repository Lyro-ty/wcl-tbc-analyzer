"""Discord-ready markdown formatting for raid summaries."""

from __future__ import annotations

from typing import Any


def format_duration(ms: int) -> str:
    """Format milliseconds as 'Xm Ys'."""
    seconds = ms // 1000
    return f"{seconds // 60}m {seconds % 60}s"


def format_raid_summary_discord(summary: dict[str, Any]) -> str:
    """Format raid night summary as Discord markdown.

    Takes the dict output from build_raid_night_summary() and formats it
    as Discord-compatible markdown text (target: <=2000 char limit).

    Args:
        summary: Dict matching the RaidNightSummary schema.

    Returns:
        Discord-formatted markdown string.
    """
    lines: list[str] = [
        f"## {summary['report_title']} \u2014 {summary['date']}",
    ]

    # Build the totals line
    kill_count = summary["total_kills"]
    boss_count = summary["total_bosses"]
    clear_time = format_duration(summary["total_clear_time_ms"])
    wipes = summary["total_wipes"]
    lines.append(
        f"**{kill_count}/{boss_count} bosses** | "
        f"Clear: {clear_time} | Wipes: {wipes}"
    )
    lines.append("")

    # Highlights section
    lines.append("**Highlights:**")

    top_dps = summary.get("top_dps_overall")
    if top_dps:
        lines.append(
            f"\u2694\ufe0f Top DPS: **{top_dps['player']}** "
            f"({top_dps['dps']:,.0f} on {top_dps['encounter']})"
        )

    most_improved = summary.get("most_improved")
    if most_improved:
        lines.append(
            f"\U0001f4c8 Most Improved: **{most_improved['player']}** "
            f"(+{most_improved['parse_delta']:.0f}% on "
            f"{most_improved['encounter']})"
        )

    biggest_regression = summary.get("biggest_regression")
    if biggest_regression:
        lines.append(
            f"\U0001f4c9 Biggest Drop: **{biggest_regression['player']}** "
            f"({biggest_regression['parse_delta']:.0f}% on "
            f"{biggest_regression['encounter']})"
        )

    mvp = summary.get("mvp_interrupts")
    if mvp:
        lines.append(
            f"\U0001f6e1\ufe0f Interrupt MVP: **{mvp['player']}** "
            f"({mvp['total_interrupts']} interrupts)"
        )

    fastest = summary.get("fastest_kill")
    if fastest and fastest.get("duration_ms"):
        lines.append(
            f"\u26a1 Fastest Kill: {fastest['encounter']} "
            f"({format_duration(fastest['duration_ms'])})"
        )

    # Week-over-week
    clear_delta = summary.get("clear_time_delta_ms")
    if clear_delta is not None:
        direction = "faster" if clear_delta < 0 else "slower"
        lines.append(
            f"\u23f1\ufe0f {format_duration(abs(clear_delta))} {direction} "
            f"than last week"
        )

    return "\n".join(lines)
