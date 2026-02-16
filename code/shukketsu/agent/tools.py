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
]
