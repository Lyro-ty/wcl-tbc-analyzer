"""LangGraph agent tools for querying raid performance data."""

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.db import queries as q

# Module-level session provider, set during app startup
_session_factory = None


async def _get_session() -> AsyncSession:
    """Get a DB session. In production, uses the app's session factory."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call set_session_factory() first.")
    session = _session_factory()
    return session


def set_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


def _format_duration(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 60}m {seconds % 60}s"


@tool
async def get_my_performance(encounter_name: str, player_name: str) -> str:
    """Get a player's recent performance data for a specific encounter.
    Returns DPS, parse percentile, deaths, and other metrics."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.MY_PERFORMANCE,
            {"encounter_name": f"%{encounter_name}%", "player_name": f"%{player_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return f"No performance data found for '{player_name}' on '{encounter_name}'."

        lines = [f"Performance for {player_name} on {encounter_name}:\n"]
        for r in rows:
            outcome = "Kill" if r.kill else "Wipe"
            lines.append(
                f"- {r.player_spec} {r.player_class} | DPS: {r.dps:,.1f} | "
                f"Parse: {r.parse_percentile}% (iLvl: {r.ilvl_parse_percentile}%) | "
                f"Deaths: {r.deaths} | iLvl: {r.item_level} | "
                f"{outcome} in {_format_duration(r.duration_ms)}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_top_rankings(encounter_name: str, class_name: str, spec_name: str) -> str:
    """Get top player rankings for a specific encounter, class, and spec.
    Returns the top 10 players with their DPS, guild, and item level."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.TOP_RANKINGS,
            {"encounter_name": f"%{encounter_name}%", "class_name": f"%{class_name}%",
             "spec_name": f"%{spec_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return f"No top rankings found for {spec_name} {class_name} on {encounter_name}."

        lines = [f"Top {spec_name} {class_name} rankings on {encounter_name}:\n"]
        for r in rows:
            lines.append(
                f"#{r.rank_position} {r.player_name} ({r.player_server}) | "
                f"DPS: {r.amount:,.1f} | iLvl: {r.item_level} | "
                f"Duration: {_format_duration(r.duration_ms)} | Guild: {r.guild_name}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def compare_to_top(
    encounter_name: str, player_name: str, class_name: str, spec_name: str,
) -> str:
    """Compare a player's performance to top rankings for the same class/spec.
    Shows side-by-side metrics for the player vs top 10 average."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.COMPARE_TO_TOP,
            {"encounter_name": f"%{encounter_name}%", "player_name": f"%{player_name}%",
             "class_name": f"%{class_name}%", "spec_name": f"%{spec_name}%"},
        )
        row = result.fetchone()
        if not row or row.dps is None:
            return f"No comparison data found for {player_name} on {encounter_name}."

        gap = ((row.avg_dps - row.dps) / row.avg_dps * 100) if row.avg_dps else 0
        return (
            f"Comparison for {player_name} ({row.player_spec} {row.player_class}) "
            f"on {encounter_name}:\n"
            f"  Your DPS: {row.dps:,.1f} | Parse: {row.parse_percentile}%\n"
            f"  Top 10 avg DPS: {row.avg_dps:,.1f} "
            f"(range: {row.min_dps:,.1f} - {row.max_dps:,.1f})\n"
            f"  Gap to top avg: {gap:.1f}%\n"
            f"  Your iLvl: {row.item_level} | Top avg iLvl: {row.avg_ilvl:.0f}\n"
            f"  Your deaths: {row.deaths}"
        )
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_fight_details(report_code: str, fight_id: int) -> str:
    """Get detailed breakdown of all player performances in a specific fight.
    Shows every player's DPS, parse, deaths, and utility metrics."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_DETAILS,
            {"report_code": report_code, "fight_id": fight_id},
        )
        rows = result.fetchall()
        if not rows:
            return f"No data found for fight {fight_id} in report {report_code}."

        first = rows[0]
        outcome = "Kill" if first.kill else "Wipe"
        lines = [
            f"Fight: {first.encounter_name} ({outcome}, "
            f"{_format_duration(first.duration_ms)}) — {first.report_title}\n"
        ]
        for r in rows:
            lines.append(
                f"  {r.player_name} ({r.player_spec} {r.player_class}) | "
                f"DPS: {r.dps:,.1f} | Parse: {r.parse_percentile}% | "
                f"Deaths: {r.deaths} | Int: {r.interrupts} | Disp: {r.dispels}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_progression(character_name: str, encounter_name: str) -> str:
    """Get time-series progression data for a character on an encounter.
    Shows best/median parse and DPS over time."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.PROGRESSION,
            {"character_name": f"%{character_name}%",
             "encounter_name": f"%{encounter_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return f"No progression data found for {character_name} on {encounter_name}."

        lines = [f"Progression for {rows[0].character_name} on {rows[0].encounter_name}:\n"]
        for r in rows:
            lines.append(
                f"  {r.time.strftime('%Y-%m-%d')} | Best Parse: {r.best_parse}% | "
                f"Median: {r.median_parse}% | Best DPS: {r.best_dps:,.1f} | "
                f"Kills: {r.kill_count} | Avg Deaths: {r.avg_deaths:.1f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_deaths_and_mechanics(encounter_name: str) -> str:
    """Get death and mechanic failure analysis for an encounter.
    Shows who died, how often, and their interrupt/dispel contributions."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.DEATHS_AND_MECHANICS,
            {"encounter_name": f"%{encounter_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return f"No death/mechanic data found for {encounter_name}."

        lines = [f"Deaths and mechanics on {encounter_name}:\n"]
        for r in rows:
            outcome = "Kill" if r.kill else "Wipe"
            lines.append(
                f"  {r.player_name} ({r.player_spec} {r.player_class}) | "
                f"Deaths: {r.deaths} | Int: {r.interrupts} | Disp: {r.dispels} | "
                f"{outcome} ({_format_duration(r.duration_ms)})"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_raid_summary(report_code: str) -> str:
    """Get an overview of all boss fights in a raid report.
    Shows each encounter with kill/wipe status, duration, and player count."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.RAID_SUMMARY, {"report_code": report_code},
        )
        rows = result.fetchall()
        if not rows:
            return f"No data found for report {report_code}."

        lines = [f"Raid summary for report {report_code}:\n"]
        for r in rows:
            outcome = "Kill" if r.kill else "Wipe"
            lines.append(
                f"  #{r.fight_id} {r.encounter_name} | {outcome} | "
                f"{_format_duration(r.duration_ms)} | {r.player_count} players"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def search_fights(encounter_name: str) -> str:
    """Search for recent fights by encounter name.
    Returns matching fights across all reports, newest first."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.SEARCH_FIGHTS,
            {"encounter_name": f"%{encounter_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return f"No fights found matching '{encounter_name}'."

        lines = [f"Fights matching '{encounter_name}':\n"]
        for r in rows:
            outcome = "Kill" if r.kill else "Wipe"
            lines.append(
                f"  {r.report_code}#{r.fight_id} {r.encounter_name} | "
                f"{outcome} | {_format_duration(r.duration_ms)} | {r.report_title}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_spec_leaderboard(encounter_name: str) -> str:
    """Get a leaderboard of all class/spec combinations ranked by average DPS on an encounter.
    Shows avg DPS, max DPS, median DPS, avg parse percentile, and sample size for each spec."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.SPEC_LEADERBOARD,
            {"encounter_name": f"%{encounter_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return f"No spec performance data found for '{encounter_name}'."

        lines = [f"Spec DPS leaderboard on {encounter_name} (kills only):\n"]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"#{i} {r.player_spec} {r.player_class} | "
                f"Avg DPS: {r.avg_dps:,.1f} | Max: {r.max_dps:,.1f} | "
                f"Median: {r.median_dps:,.1f} | Avg Parse: {r.avg_parse}% | "
                f"iLvl: {r.avg_ilvl} | n={r.sample_size}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def compare_raid_to_top(report_code: str) -> str:
    """Compare a raid's boss kills to WCL global top speed rankings.
    Shows per-boss time gaps, execution metrics, and a full-clear summary."""
    session = await _get_session()
    try:
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
                f"  {r.encounter_name} | Your time: {_format_duration(r.duration_ms)} | "
                f"Deaths: {r.total_deaths} | Int: {r.total_interrupts} | "
                f"Disp: {r.total_dispels} | Avg DPS: {r.avg_dps:,.1f}"
            )
            if r.top10_avg_ms:
                total_top10 += r.top10_avg_ms
                gap_pct = ((r.duration_ms - r.top10_avg_ms) / r.top10_avg_ms * 100)
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
                f"  Estimated top 10 clear time: {_format_duration(int(total_top10))}"
                f" | Gap: {clear_gap:+.1f}%"
            )
        lines.append(f"  Total deaths across raid: {total_deaths}")
        lines.append(f"  Bosses killed: {len(rows)}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def compare_two_raids(report_a: str, report_b: str) -> str:
    """Compare two raid reports side-by-side. Shows per-boss kill times,
    deaths, DPS, composition, and highlights which raid was faster/cleaner."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.COMPARE_TWO_RAIDS, {"report_a": report_a, "report_b": report_b},
        )
        rows = result.fetchall()
        if not rows:
            return f"No kill data found for reports {report_a} and/or {report_b}."

        lines = [f"Raid Comparison — {report_a} (A) vs {report_b} (B):\n"]
        for r in rows:
            boss_line = f"  {r.encounter_name}:"
            a_time = f" A: {_format_duration(r.a_duration_ms)}" if r.a_duration_ms else " A: —"
            b_time = f" B: {_format_duration(r.b_duration_ms)}" if r.b_duration_ms else " B: —"
            boss_line += f"{a_time},{b_time}"

            if r.a_duration_ms and r.b_duration_ms:
                diff_ms = r.a_duration_ms - r.b_duration_ms
                diff_s = abs(diff_ms) // 1000
                faster = "B" if diff_ms > 0 else "A"
                boss_line += f" | {faster} faster by {diff_s}s"

            a_deaths = r.a_deaths if r.a_deaths is not None else "—"
            b_deaths = r.b_deaths if r.b_deaths is not None else "—"
            boss_line += f" | Deaths A: {a_deaths}, B: {b_deaths}"

            a_dps = f"{r.a_avg_dps:,.1f}" if r.a_avg_dps else "—"
            b_dps = f"{r.b_avg_dps:,.1f}" if r.b_avg_dps else "—"
            boss_line += f" | Avg DPS A: {a_dps}, B: {b_dps}"

            lines.append(boss_line)

            if r.a_comp != r.b_comp and r.a_comp and r.b_comp:
                lines.append(f"    Comp A: {r.a_comp}")
                lines.append(f"    Comp B: {r.b_comp}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_raid_execution(report_code: str) -> str:
    """Get execution quality metrics for a full raid. Shows deaths, interrupts,
    dispels, DPS, and parse percentiles per boss with raid-wide totals."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.RAID_EXECUTION_SUMMARY, {"report_code": report_code},
        )
        rows = result.fetchall()
        if not rows:
            return f"No kill data found for report {report_code}."

        total_deaths = sum(r.total_deaths or 0 for r in rows)
        total_interrupts = sum(r.total_interrupts or 0 for r in rows)
        total_dispels = sum(r.total_dispels or 0 for r in rows)

        lines = [
            f"Raid Execution Summary — report {report_code}:",
            f"  Bosses killed: {len(rows)} | Total deaths: {total_deaths}"
            f" | Total interrupts: {total_interrupts} | Total dispels: {total_dispels}\n",
        ]
        for r in rows:
            parse_str = f"{r.avg_parse}%" if r.avg_parse is not None else "N/A"
            ilvl_str = f"{r.avg_ilvl}" if r.avg_ilvl is not None else "N/A"
            lines.append(
                f"  {r.encounter_name} ({_format_duration(r.duration_ms)}) | "
                f"Deaths: {r.total_deaths} (avg {r.avg_deaths_per_player}/player) | "
                f"Int: {r.total_interrupts} | Disp: {r.total_dispels} | "
                f"Raid DPS: {r.raid_total_dps:,.1f} (avg {r.raid_avg_dps:,.1f}) | "
                f"Parse: {parse_str} | iLvl: {ilvl_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_ability_breakdown(report_code: str, fight_id: int, player_name: str) -> str:
    """Get a player's ability breakdown for a specific fight.
    Shows top damage and healing abilities with crit%, hit count, and % of total.
    Use this to analyze rotation quality, ability priorities, and damage sources.
    Requires table data to have been ingested with --with-tables."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.ABILITY_BREAKDOWN,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return (
                f"No ability data found for '{player_name}' in fight {fight_id} "
                f"of report {report_code}. Table data may not have been ingested yet "
                f"(use pull-my-logs --with-tables or pull-table-data to fetch it)."
            )

        damage_rows = [r for r in rows if r.metric_type == "damage"]
        healing_rows = [r for r in rows if r.metric_type == "healing"]

        lines = [f"Ability breakdown for {player_name} in {report_code}#{fight_id}:\n"]

        if damage_rows:
            lines.append("Damage abilities:")
            for r in damage_rows[:10]:
                lines.append(
                    f"  {r.ability_name} | {r.pct_of_total}% of total | "
                    f"Total: {r.total:,} | Hits: {r.hit_count} | "
                    f"Crit: {r.crit_pct}%"
                )

        if healing_rows:
            lines.append("\nHealing abilities:")
            for r in healing_rows[:8]:
                lines.append(
                    f"  {r.ability_name} | {r.pct_of_total}% of total | "
                    f"Total: {r.total:,} | Hits: {r.hit_count} | "
                    f"Crit: {r.crit_pct}%"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_buff_analysis(report_code: str, fight_id: int, player_name: str) -> str:
    """Get a player's buff and debuff uptimes for a specific fight.
    Shows buff/debuff uptime percentages to identify missing buffs or low uptimes.
    Use this to analyze buff management, consumable usage, and debuff application.
    Requires table data to have been ingested with --with-tables."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.BUFF_ANALYSIS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return (
                f"No buff/debuff data found for '{player_name}' in fight {fight_id} "
                f"of report {report_code}. Table data may not have been ingested yet "
                f"(use pull-my-logs --with-tables or pull-table-data to fetch it)."
            )

        buff_rows = [r for r in rows if r.metric_type == "buff"]
        debuff_rows = [r for r in rows if r.metric_type == "debuff"]

        lines = [f"Buff/debuff analysis for {player_name} in {report_code}#{fight_id}:\n"]

        if buff_rows:
            lines.append("Buffs:")
            for r in buff_rows[:15]:
                tier = "HIGH" if r.uptime_pct >= 90 else "MED" if r.uptime_pct >= 50 else "LOW"
                lines.append(
                    f"  [{tier}] {r.ability_name} | Uptime: {r.uptime_pct}%"
                )

        if debuff_rows:
            lines.append("\nDebuffs applied:")
            for r in debuff_rows[:10]:
                lines.append(
                    f"  {r.ability_name} | Uptime: {r.uptime_pct}%"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_death_analysis(
    report_code: str, fight_id: int, player_name: str | None = None,
) -> str:
    """Get detailed death recaps for a specific fight. Shows killing blow,
    source, damage taken, and last damage events before each death.
    Use this to understand WHY players died and whether deaths were avoidable.
    Requires event data to have been ingested with --with-events."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.DEATH_ANALYSIS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%" if player_name else None},
        )
        rows = result.fetchall()
        if not rows:
            return (
                f"No death data found for fight {fight_id} in report {report_code}. "
                f"Event data may not have been ingested yet "
                f"(use pull-my-logs --with-events or pull-event-data to fetch it)."
            )

        import json
        lines = [
            f"Death analysis for {rows[0].encounter_name} "
            f"({report_code}#{fight_id}):\n"
        ]
        for r in rows:
            ts_sec = r.timestamp_ms / 1000
            lines.append(
                f"  {r.player_name} (death #{r.death_index}) at {ts_sec:.1f}s:"
            )
            lines.append(
                f"    Killing blow: {r.killing_blow_ability} "
                f"from {r.killing_blow_source}"
            )
            lines.append(f"    Total damage taken: {r.damage_taken_total:,}")

            events = json.loads(r.events_json) if r.events_json else []
            if events:
                lines.append("    Last damage events:")
                for e in events[-5:]:
                    e_ts = e.get("ts", 0) / 1000
                    lines.append(
                        f"      {e_ts:.1f}s: {e.get('ability', '?')} "
                        f"({e.get('amount', 0):,} from {e.get('source', '?')})"
                    )
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_activity_report(
    report_code: str, fight_id: int, player_name: str | None = None,
) -> str:
    """Get GCD uptime / 'Always Be Casting' analysis for players in a fight.
    Shows casting efficiency, downtime gaps, and casts per minute.
    Requires event data to have been ingested with --with-events."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.CAST_ACTIVITY,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%" if player_name else None},
        )
        rows = result.fetchall()
        if not rows:
            return (
                f"No cast activity data found for fight {fight_id} in report {report_code}. "
                f"Event data may not have been ingested yet "
                f"(use pull-my-logs --with-events or pull-event-data to fetch it)."
            )

        lines = [
            f"Cast activity (ABC) analysis for {rows[0].encounter_name} "
            f"({report_code}#{fight_id}):\n"
        ]
        for r in rows:
            if r.gcd_uptime_pct >= 90:
                grade = "EXCELLENT"
            elif r.gcd_uptime_pct >= 85:
                grade = "GOOD"
            elif r.gcd_uptime_pct >= 75:
                grade = "FAIR"
            else:
                grade = "NEEDS WORK"

            gap_str = _format_duration(r.longest_gap_ms) if r.longest_gap_ms else "none"
            lines.append(
                f"  [{grade}] {r.player_name} | GCD uptime: {r.gcd_uptime_pct}% | "
                f"Casts: {r.total_casts} ({r.casts_per_minute}/min) | "
                f"Longest gap: {gap_str} | Gaps >2.5s: {r.gap_count}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_cooldown_efficiency(
    report_code: str, fight_id: int, player_name: str | None = None,
) -> str:
    """Get cooldown usage efficiency for players in a fight.
    Shows how many times each major cooldown was used vs max possible.
    Requires event data to have been ingested with --with-events."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.COOLDOWN_EFFICIENCY,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%" if player_name else None},
        )
        rows = result.fetchall()
        if not rows:
            return (
                f"No cooldown data found for fight {fight_id} in report {report_code}. "
                f"Event data may not have been ingested yet "
                f"(use pull-my-logs --with-events or pull-event-data to fetch it)."
            )

        lines = [
            f"Cooldown efficiency for {rows[0].encounter_name} "
            f"({report_code}#{fight_id}):\n"
        ]

        current_player = None
        for r in rows:
            if r.player_name != current_player:
                current_player = r.player_name
                lines.append(f"  {r.player_name}:")

            if r.efficiency_pct < 70:
                flag = "[LOW]"
            elif r.efficiency_pct >= 90:
                flag = "[GOOD]"
            else:
                flag = "[OK]"

            first_use = f"{r.first_use_ms / 1000:.1f}s" if r.first_use_ms else "never"
            lines.append(
                f"    {flag} {r.ability_name} ({r.cooldown_sec}s CD): "
                f"{r.times_used}/{r.max_possible_uses} uses "
                f"({r.efficiency_pct}%) | First use: {first_use}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_consumable_check(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Check a player's consumable and preparation buff usage for a fight.
    Compares buff uptimes against expected consumables for the player's spec/role.
    Shows present consumables with uptimes and flags missing ones.
    Requires table data to have been ingested with --with-tables."""
    from shukketsu.pipeline.constants import (
        ROLE_BY_SPEC,
        get_expected_consumables,
    )

    session = await _get_session()
    try:
        # Get player's spec from fight_performances
        perf_result = await session.execute(
            q.FIGHT_DETAILS,
            {"report_code": report_code, "fight_id": fight_id},
        )
        perf_rows = perf_result.fetchall()
        player_row = None
        for r in perf_rows:
            if r.player_name.lower() == player_name.lower():
                player_row = r
                break
        if not player_row:
            return f"No performance data found for '{player_name}' in fight {fight_id}."

        spec = player_row.player_spec
        role = ROLE_BY_SPEC.get(spec, "melee_dps")
        expected = get_expected_consumables(spec)

        # Get actual buff uptimes
        result = await session.execute(
            q.CONSUMABLE_CHECK,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player_name},
        )
        rows = result.fetchall()

        actual_by_id: dict[int, tuple[str, float]] = {}
        for r in rows:
            actual_by_id[r.spell_id] = (r.ability_name, r.uptime_pct)

        # Match expected consumables against actual buffs
        present = []
        missing = []
        for c in expected:
            if c.spell_id in actual_by_id:
                name, uptime = actual_by_id[c.spell_id]
                present.append(f"  [OK] {c.name} ({c.category}) | Uptime: {uptime}%")
            else:
                missing.append(f"  [MISSING] {c.name} ({c.category})")

        lines = [
            f"Consumable check for {player_name} ({spec}, role: {role}) "
            f"in {report_code}#{fight_id}:\n"
        ]

        if present:
            lines.append("Present consumables:")
            lines.extend(present)

        if missing:
            lines.append("\nMissing consumables:")
            lines.extend(missing)

        if not present and not missing:
            lines.append("No consumable data available (table data may not be ingested).")

        score = len(present) / max(len(present) + len(missing), 1) * 100
        lines.append(f"\nPrep score: {score:.0f}% ({len(present)}/{len(present) + len(missing)})")

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_overheal_analysis(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get overhealing analysis for a healer in a specific fight.
    Shows per-ability overheal percentage and total overhealing.
    Abilities with >30% overheal indicate potential wasted GCDs or poor healing targeting.
    Requires table data to have been ingested with --with-tables."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.OVERHEAL_ANALYSIS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            return (
                f"No healing data found for '{player_name}' in fight {fight_id} "
                f"of report {report_code}. Table data may not have been ingested yet "
                f"(use pull-my-logs --with-tables or pull-table-data to fetch it)."
            )

        total_heal = sum(r.total for r in rows)
        total_overheal = sum(r.overheal_total or 0 for r in rows)
        grand_total = total_heal + total_overheal
        total_overheal_pct = (
            (total_overheal / grand_total * 100) if grand_total > 0 else 0
        )

        lines = [
            f"Overhealing analysis for {player_name} in {report_code}#{fight_id}:\n",
            f"Total effective healing: {total_heal:,}",
            f"Total overhealing: {total_overheal:,} ({total_overheal_pct:.1f}%)\n",
            "Per-ability breakdown:",
        ]

        for r in rows:
            overheal_amt = r.overheal_total or 0
            oh_pct = float(r.overheal_pct) if r.overheal_pct else 0
            flag = ""
            if oh_pct >= 50:
                flag = " [HIGH]"
            elif oh_pct >= 30:
                flag = " [MODERATE]"
            lines.append(
                f"  {r.ability_name} | Effective: {r.total:,} | "
                f"Overheal: {overheal_amt:,} ({oh_pct:.1f}%){flag}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_cancelled_casts(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get cancelled cast analysis for a player in a fight.
    Shows how many casts were started but not completed
    (interrupted, moved, or manually cancelled).
    High cancel rates (>10%) indicate movement or cast decisions.
    Requires event data to have been ingested with --with-events."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.CANCELLED_CASTS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player_name},
        )
        row = result.fetchone()
        if not row:
            return (
                f"No cancelled cast data found for '{player_name}' in fight {fight_id} "
                f"of report {report_code}. Event data may not have been ingested yet."
            )

        import json

        lines = [
            f"Cancelled cast analysis for {player_name} in {report_code}#{fight_id}:\n",
            f"  Total cast begins: {row.total_begins}",
            f"  Successful casts: {row.total_completions}",
            f"  Cancelled casts: {row.cancel_count} ({row.cancel_pct}%)",
        ]

        if row.cancel_pct < 5:
            grade = "EXCELLENT"
        elif row.cancel_pct < 10:
            grade = "GOOD"
        elif row.cancel_pct < 20:
            grade = "FAIR"
        else:
            grade = "NEEDS WORK"
        lines.append(f"  Grade: [{grade}]")

        if row.top_cancelled_json:
            top = json.loads(row.top_cancelled_json)
            if top:
                lines.append("\n  Most cancelled abilities:")
                for entry in top:
                    lines.append(
                        f"    Spell ID {entry['spell_id']}: {entry['count']} cancels"
                    )

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


@tool
async def get_personal_bests(
    player_name: str, encounter_name: str | None = None,
) -> str:
    """Get a player's personal records (best DPS, parse, HPS) per encounter.
    Shows PR values and kill count per boss. Useful for tracking personal progression."""
    session = await _get_session()
    try:
        if encounter_name:
            result = await session.execute(
                q.PERSONAL_BESTS_BY_ENCOUNTER,
                {"player_name": f"%{player_name}%",
                 "encounter_name": f"%{encounter_name}%"},
            )
        else:
            result = await session.execute(
                q.PERSONAL_BESTS,
                {"player_name": f"%{player_name}%"},
            )
        rows = result.fetchall()
        if not rows:
            return f"No personal bests found for '{player_name}'."

        lines = [f"Personal bests for {player_name}:\n"]
        for r in rows:
            parse_str = f"{r.best_parse}%" if r.best_parse is not None else "N/A"
            ilvl_str = f"{r.peak_ilvl}" if r.peak_ilvl is not None else "N/A"
            lines.append(
                f"{r.encounter_name}: Best DPS {r.best_dps:,.1f} | "
                f"Best Parse {parse_str} | Best HPS {r.best_hps:,.1f} | "
                f"Kills: {r.kill_count} | Peak iLvl: {ilvl_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()


ALL_TOOLS = [
    get_my_performance,
    get_top_rankings,
    compare_to_top,
    get_fight_details,
    get_progression,
    get_deaths_and_mechanics,
    get_raid_summary,
    search_fights,
    get_spec_leaderboard,
    compare_raid_to_top,
    compare_two_raids,
    get_raid_execution,
    get_ability_breakdown,
    get_buff_analysis,
    get_death_analysis,
    get_activity_report,
    get_cooldown_efficiency,
    get_consumable_check,
    get_overheal_analysis,
    get_cancelled_casts,
    get_personal_bests,
]
