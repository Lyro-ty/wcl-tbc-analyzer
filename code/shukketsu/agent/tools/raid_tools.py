"""Raid-level comparison agent tools (3 tools)."""

from shukketsu.agent.tool_utils import _format_duration, db_tool
from shukketsu.db import queries as q


@db_tool
async def compare_raid_to_top(session, report_code: str) -> str:
    """Compare a raid's boss kills to WCL global top speed rankings.
    Shows per-boss time gaps, execution metrics, and a full-clear summary."""
    result = await session.execute(
        q.RAID_VS_TOP_SPEED, {"report_code": report_code},
    )
    rows = result.fetchall()
    if not rows:
        return f"No kill data found for report {report_code}."

    lines = [f"Raid vs Top Speed Rankings — report {report_code}:\n"]
    total_duration = 0
    total_top10 = 0
    total_deaths = 0
    for r in rows:
        total_duration += r.duration_ms
        total_deaths += r.total_deaths or 0
        boss_line = (
            f"  {r.encounter_name} | "
            f"Your time: {_format_duration(r.duration_ms)} | "
            f"Deaths: {r.total_deaths} | Int: {r.total_interrupts} | "
            f"Disp: {r.total_dispels} | Avg DPS: {r.avg_dps:,.1f}"
        )
        if r.top10_avg_ms:
            total_top10 += r.top10_avg_ms
            gap_pct = (
                (r.duration_ms - r.top10_avg_ms) / r.top10_avg_ms * 100
            )
            boss_line += (
                f" | WR: {_format_duration(r.world_record_ms)}"
                f" | Top10 avg: {_format_duration(int(r.top10_avg_ms))}"
                f" | Gap: {gap_pct:+.1f}%"
            )
        else:
            boss_line += " | No speed ranking data available"
        lines.append(boss_line)

    lines.append("\nFull-clear summary:")
    lines.append(f"  Total clear time: {_format_duration(total_duration)}")
    if total_top10:
        clear_gap = (
            (total_duration - total_top10) / total_top10 * 100
        )
        lines.append(
            f"  Estimated top 10 clear time: "
            f"{_format_duration(int(total_top10))}"
            f" | Gap: {clear_gap:+.1f}%"
        )
    lines.append(f"  Total deaths across raid: {total_deaths}")
    lines.append(f"  Bosses killed: {len(rows)}")
    return "\n".join(lines)


@db_tool
async def compare_two_raids(
    session, report_a: str, report_b: str,
) -> str:
    """Compare two raid reports side-by-side. Shows per-boss kill times,
    deaths, DPS, composition, and highlights which raid was faster/cleaner."""
    result = await session.execute(
        q.COMPARE_TWO_RAIDS,
        {"report_a": report_a, "report_b": report_b},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No kill data found for reports {report_a} "
            f"and/or {report_b}."
        )

    lines = [
        f"Raid Comparison — {report_a} (A) vs {report_b} (B):\n"
    ]
    for r in rows:
        boss_line = f"  {r.encounter_name}:"
        a_time = (
            f" A: {_format_duration(r.a_duration_ms)}"
            if r.a_duration_ms else " A: —"
        )
        b_time = (
            f" B: {_format_duration(r.b_duration_ms)}"
            if r.b_duration_ms else " B: —"
        )
        boss_line += f"{a_time},{b_time}"

        if r.a_duration_ms and r.b_duration_ms:
            diff_ms = r.a_duration_ms - r.b_duration_ms
            diff_s = abs(diff_ms) // 1000
            faster = "B" if diff_ms > 0 else "A"
            boss_line += f" | {faster} faster by {diff_s}s"

        a_deaths = (
            r.a_deaths if r.a_deaths is not None else "\u2014"
        )
        b_deaths = (
            r.b_deaths if r.b_deaths is not None else "\u2014"
        )
        boss_line += f" | Deaths A: {a_deaths}, B: {b_deaths}"

        a_dps = f"{r.a_avg_dps:,.1f}" if r.a_avg_dps else "\u2014"
        b_dps = f"{r.b_avg_dps:,.1f}" if r.b_avg_dps else "\u2014"
        boss_line += f" | Avg DPS A: {a_dps}, B: {b_dps}"

        lines.append(boss_line)

        if r.a_comp != r.b_comp and r.a_comp and r.b_comp:
            lines.append(f"    Comp A: {r.a_comp}")
            lines.append(f"    Comp B: {r.b_comp}")

    return "\n".join(lines)


@db_tool
async def get_raid_execution(session, report_code: str) -> str:
    """Get raid overview and execution quality metrics for a full raid. Shows
    kills AND wipes with deaths, interrupts, dispels, DPS, and parse
    percentiles per fight. Also serves as a raid summary."""
    result = await session.execute(
        q.RAID_EXECUTION_SUMMARY, {"report_code": report_code},
    )
    rows = result.fetchall()
    if not rows:
        return f"No fight data found for report {report_code}."

    kills = [r for r in rows if r.kill]
    wipes = [r for r in rows if not r.kill]
    total_deaths = sum(r.total_deaths or 0 for r in rows)
    total_interrupts = sum(r.total_interrupts or 0 for r in rows)
    total_dispels = sum(r.total_dispels or 0 for r in rows)

    lines = [
        f"Raid Execution Summary — report {report_code}:",
        f"  Fights: {len(rows)} ({len(kills)} kills, {len(wipes)} wipes)"
        f" | Total deaths: {total_deaths}"
        f" | Total interrupts: {total_interrupts}"
        f" | Total dispels: {total_dispels}\n",
    ]

    if kills:
        lines.append("Kills:")
        for r in kills:
            lines.append(_format_fight_line(r))

    if wipes:
        lines.append("\nWipes:")
        for r in wipes:
            lines.append(_format_fight_line(r))

    return "\n".join(lines)


def _format_fight_line(r) -> str:
    """Format a single fight row for display."""
    status = "KILL" if r.kill else "WIPE"
    parse_str = (
        f"{r.avg_parse}%" if r.avg_parse is not None else "N/A"
    )
    ilvl_str = (
        f"{r.avg_ilvl}" if r.avg_ilvl is not None else "N/A"
    )
    dps_str = (
        f"Raid DPS: {r.raid_total_dps:,.1f} (avg {r.raid_avg_dps:,.1f})"
        if r.raid_total_dps else "DPS: N/A"
    )
    deaths_str = (
        f"Deaths: {r.total_deaths} (avg {r.avg_deaths_per_player}/player)"
        if r.total_deaths is not None else "Deaths: N/A"
    )
    return (
        f"  [{status}] {r.encounter_name} "
        f"({_format_duration(r.duration_ms)}) | "
        f"{deaths_str} | "
        f"Int: {r.total_interrupts or 0} | "
        f"Disp: {r.total_dispels or 0} | "
        f"{dps_str} | "
        f"Parse: {parse_str} | iLvl: {ilvl_str}"
    )
