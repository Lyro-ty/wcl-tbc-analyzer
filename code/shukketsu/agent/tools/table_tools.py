"""Table-data agent tools requiring --with-tables ingestion (4 tools)."""

from shukketsu.agent.tool_utils import TABLE_DATA_HINT, db_tool, grade_above, wildcard
from shukketsu.db import queries as q


@db_tool
async def get_ability_breakdown(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get a player's ability breakdown for a specific fight.
    Shows top damage and healing abilities with crit%, hit count, and % of total.
    Use this to analyze rotation quality, ability priorities, and damage sources.
    Requires table data to have been ingested with --with-tables."""
    result = await session.execute(
        q.ABILITY_BREAKDOWN,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No ability data found for '{player_name}' in fight "
            f"{fight_id} of report {report_code}. {TABLE_DATA_HINT}"
        )

    damage_rows = [r for r in rows if r.metric_type == "damage"]
    healing_rows = [r for r in rows if r.metric_type == "healing"]

    lines = [
        f"Ability breakdown for {player_name} "
        f"in {report_code}#{fight_id}:\n"
    ]

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


@db_tool
async def get_buff_analysis(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get a player's buff and debuff uptimes for a specific fight.
    Shows buff/debuff uptime percentages to identify missing buffs or low
    uptimes. Use this to analyze buff management, consumable usage, and debuff
    application. Requires table data to have been ingested with --with-tables."""
    result = await session.execute(
        q.BUFF_ANALYSIS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No buff/debuff data found for '{player_name}' in fight "
            f"{fight_id} of report {report_code}. {TABLE_DATA_HINT}"
        )

    buff_rows = [r for r in rows if r.metric_type == "buff"]
    debuff_rows = [r for r in rows if r.metric_type == "debuff"]

    lines = [
        f"Buff/debuff analysis for {player_name} "
        f"in {report_code}#{fight_id}:\n"
    ]

    if buff_rows:
        lines.append("Buffs:")
        for r in buff_rows[:15]:
            tier = grade_above(r.uptime_pct, [(90, "HIGH"), (50, "MED")], "LOW")
            lines.append(
                f"  [{tier}] {r.ability_name} | "
                f"Uptime: {r.uptime_pct}%"
            )

    if debuff_rows:
        lines.append("\nDebuffs applied:")
        for r in debuff_rows[:10]:
            lines.append(
                f"  {r.ability_name} | Uptime: {r.uptime_pct}%"
            )

    return "\n".join(lines)


@db_tool
async def get_overheal_analysis(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get overhealing analysis for a healer in a specific fight.
    Shows per-ability overheal percentage and total overhealing.
    Abilities with >30% overheal indicate potential wasted GCDs or poor
    healing targeting. Requires table data to have been ingested with
    --with-tables."""
    result = await session.execute(
        q.OVERHEAL_ANALYSIS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No healing data found for '{player_name}' in fight "
            f"{fight_id} of report {report_code}. {TABLE_DATA_HINT}"
        )

    total_heal = sum(r.total for r in rows)
    total_overheal = sum(r.overheal_total or 0 for r in rows)
    grand_total = total_heal + total_overheal
    total_overheal_pct = (
        (total_overheal / grand_total * 100) if grand_total > 0 else 0
    )

    lines = [
        f"Overhealing analysis for {player_name} "
        f"in {report_code}#{fight_id}:\n",
        f"Total effective healing: {total_heal:,}",
        f"Total overhealing: {total_overheal:,} "
        f"({total_overheal_pct:.1f}%)\n",
        "Per-ability breakdown:",
    ]

    for r in rows:
        overheal_amt = r.overheal_total or 0
        oh_pct = float(r.overheal_pct) if r.overheal_pct else 0
        flag = grade_above(oh_pct, [(50, " [HIGH]"), (30, " [MODERATE]")], "")
        lines.append(
            f"  {r.ability_name} | Effective: {r.total:,} | "
            f"Overheal: {overheal_amt:,} ({oh_pct:.1f}%){flag}"
        )

    return "\n".join(lines)


@db_tool
async def get_trinket_performance(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get trinket proc uptime analysis for a player in a fight.
    Compares actual uptime against expected for known trinkets.
    Requires table data ingestion."""
    from shukketsu.pipeline.constants import CLASSIC_TRINKETS

    result = await session.execute(
        q.PLAYER_BUFFS_FOR_TRINKETS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()

    entries = []
    for r in rows:
        trinket_def = CLASSIC_TRINKETS.get(r.spell_id)
        if not trinket_def:
            continue

        actual = float(r.uptime_pct)
        expected = trinket_def.expected_uptime_pct

        grade = grade_above(
            actual, [(expected, "EXCELLENT"), (expected * 0.8, "GOOD")], "POOR",
        )

        entries.append(
            f"  [{grade}] {trinket_def.name}: Uptime {actual:.1f}% "
            f"(expected {expected:.0f}%)"
        )

    if not entries:
        return (
            f"No known trinket procs found for '{player_name}' in "
            f"fight {fight_id} of report {report_code}. Either the "
            f"player has no tracked trinkets or table data has not "
            f"been ingested yet."
        )

    lines = [
        f"Trinket performance for {player_name} in "
        f"{report_code}#{fight_id}:\n"
    ]
    lines.extend(entries)
    return "\n".join(lines)
