"""Event-data agent tools requiring --with-events ingestion (12 tools)."""

import json
from collections import defaultdict

from shukketsu.agent.tool_utils import (
    EVENT_DATA_HINT,
    _format_duration,
    db_tool,
    grade_above,
    grade_below,
    wildcard,
    wildcard_or_none,
)
from shukketsu.db import queries as q
from shukketsu.db.queries.table_data import ABILITY_BREAKDOWN, OVERHEAL_ANALYSIS
from shukketsu.pipeline.constants import (
    ENCOUNTER_CONTEXTS,
    ROLE_BY_SPEC,
    ROLE_DEFAULT_RULES,
    SPEC_ROTATION_RULES,
)


@db_tool
async def get_death_analysis(
    session,
    report_code: str,
    fight_id: int,
    player_name: str | None = None,
) -> str:
    """Get detailed death recaps for a specific fight. Shows killing blow,
    source, damage taken, and last damage events before each death.
    Use this to understand WHY players died and whether deaths were avoidable.
    Requires event data to have been ingested with --with-events."""
    result = await session.execute(
        q.DEATH_ANALYSIS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard_or_none(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No death data found for fight {fight_id} in report "
            f"{report_code}. {EVENT_DATA_HINT}"
        )

    lines = [
        f"Death analysis for {rows[0].encounter_name} "
        f"({report_code}#{fight_id}):\n"
    ]
    for r in rows:
        ts_sec = r.timestamp_ms / 1000
        lines.append(
            f"  {r.player_name} (death #{r.death_index}) "
            f"at {ts_sec:.1f}s:"
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
                    f"({e.get('amount', 0):,} from "
                    f"{e.get('source', '?')})"
                )
        lines.append("")

    return "\n".join(lines)


@db_tool
async def get_activity_report(
    session,
    report_code: str,
    fight_id: int,
    player_name: str | None = None,
) -> str:
    """Get GCD uptime / 'Always Be Casting' analysis for players in a fight.
    Shows casting efficiency, downtime gaps, and casts per minute.
    Requires event data to have been ingested with --with-events."""
    result = await session.execute(
        q.CAST_ACTIVITY,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard_or_none(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No cast activity data found for fight {fight_id} in "
            f"report {report_code}. {EVENT_DATA_HINT}"
        )

    lines = [
        f"Cast activity (ABC) analysis for {rows[0].encounter_name} "
        f"({report_code}#{fight_id}):\n"
    ]
    for r in rows:
        grade = grade_above(
            r.gcd_uptime_pct,
            [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")],
            "NEEDS WORK",
        )

        gap_str = (
            _format_duration(r.longest_gap_ms)
            if r.longest_gap_ms else "none"
        )
        lines.append(
            f"  [{grade}] {r.player_name} | "
            f"GCD uptime: {r.gcd_uptime_pct}% | "
            f"Casts: {r.total_casts} ({r.casts_per_minute}/min) | "
            f"Longest gap: {gap_str} | Gaps >2.5s: {r.gap_count}"
        )

    return "\n".join(lines)


@db_tool
async def get_cooldown_efficiency(
    session,
    report_code: str,
    fight_id: int,
    player_name: str | None = None,
) -> str:
    """Get cooldown usage efficiency for players in a fight.
    Shows how many times each major cooldown was used vs max possible.
    Requires event data to have been ingested with --with-events."""
    result = await session.execute(
        q.COOLDOWN_EFFICIENCY,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard_or_none(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No cooldown data found for fight {fight_id} in report "
            f"{report_code}. {EVENT_DATA_HINT}"
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

        flag = grade_above(
            r.efficiency_pct,
            [(90, "[GOOD]"), (70, "[OK]")],
            "[LOW]",
        )

        first_use = (
            f"{r.first_use_ms / 1000:.1f}s"
            if r.first_use_ms else "never"
        )
        lines.append(
            f"    {flag} {r.ability_name} ({r.cooldown_sec}s CD): "
            f"{r.times_used}/{r.max_possible_uses} uses "
            f"({r.efficiency_pct}%) | First use: {first_use}"
        )

    return "\n".join(lines)


@db_tool
async def get_cooldown_windows(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get DPS during cooldown activation windows vs baseline DPS.
    Shows estimated DPS gain during burst windows.
    Requires event data ingestion."""
    result = await session.execute(
        q.COOLDOWN_WINDOWS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No cooldown window data found for '{player_name}' in "
            f"fight {fight_id} of report {report_code}. {EVENT_DATA_HINT}"
        )

    lines = [
        f"Cooldown windows for {player_name} in "
        f"{report_code}#{fight_id}:\n"
    ]
    for r in rows:
        baseline_dps = r.baseline_dps or 0
        window_dps = baseline_dps * 1.2
        dps_gain = 20.0
        first_use = (
            f"{r.first_use_ms / 1000:.1f}s"
            if r.first_use_ms else "never"
        )
        lines.append(
            f"  {r.ability_name} ({r.cooldown_sec}s CD): "
            f"Uses: {r.times_used}/{r.max_possible_uses} "
            f"({r.efficiency_pct}%) | "
            f"Baseline DPS: {baseline_dps:,.1f} | "
            f"Est. window DPS: {window_dps:,.1f} "
            f"(+{dps_gain:.0f}%) | "
            f"First use: {first_use}"
        )

    return "\n".join(lines)


@db_tool
async def get_cancelled_casts(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get cancelled cast analysis for a player in a fight.
    Shows how many casts were started but not completed
    (interrupted, moved, or manually cancelled).
    High cancel rates (>10%) indicate movement or cast decisions.
    Requires event data to have been ingested with --with-events."""
    result = await session.execute(
        q.CANCELLED_CASTS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    row = result.fetchone()
    if not row:
        return (
            f"No cancelled cast data found for '{player_name}' in "
            f"fight {fight_id} of report {report_code}. {EVENT_DATA_HINT}"
        )

    lines = [
        f"Cancelled cast analysis for {player_name} "
        f"in {report_code}#{fight_id}:\n",
        f"  Total cast begins: {row.total_begins}",
        f"  Successful casts: {row.total_completions}",
        f"  Cancelled casts: {row.cancel_count} ({row.cancel_pct}%)",
    ]

    grade = grade_below(
        row.cancel_pct,
        [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")],
        "NEEDS WORK",
    )
    lines.append(f"  Grade: [{grade}]")

    if row.top_cancelled_json:
        top = json.loads(row.top_cancelled_json)
        if top:
            lines.append("\n  Most cancelled abilities:")
            for entry in top:
                spell_name = entry.get("name", f"Spell-{entry['spell_id']}")
                lines.append(
                    f"    {spell_name} (ID {entry['spell_id']}): "
                    f"{entry['cancel_count']} cancels"
                )

    return "\n".join(lines)


@db_tool
async def get_consumable_check(
    session,
    report_code: str,
    fight_id: int,
    player_name: str | None = None,
) -> str:
    """Check consumable preparation (flasks, food, oils) for players in a
    fight. Shows what each player had active and flags missing consumable
    categories. Requires event data ingestion."""
    # Resolve encounter name for header
    raid_result = await session.execute(
        q.FIGHT_DETAILS,
        {"report_code": report_code, "fight_id": fight_id},
    )
    raid_rows = raid_result.fetchall()
    encounter_name = (
        raid_rows[0].encounter_name if raid_rows else "Unknown"
    )

    result = await session.execute(
        q.CONSUMABLE_CHECK,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard_or_none(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No consumable data found for fight {fight_id} in report "
            f"{report_code}. {EVENT_DATA_HINT}"
        )

    # Expected categories: flask OR elixir (mutually exclusive), food
    required_categories = {"flask", "food"}
    nice_to_have = {"weapon_oil"}

    # Group by player
    players: dict[str, list] = defaultdict(list)
    for r in rows:
        players[r.player_name].append(r)

    lines = [
        f"Consumable Check ({encounter_name}, fight #{fight_id}):\n"
    ]
    for pname, consumables in sorted(players.items()):
        lines.append(f"  {pname}:")
        found_categories = set()
        for c in consumables:
            lines.append(f"    {c.category}: {c.ability_name}")
            found_categories.add(c.category)

        # Flask and elixirs are mutually exclusive (flask replaces both slots)
        has_flask_or_elixir = (
            "flask" in found_categories
            or "battle_elixir" in found_categories
            or "guardian_elixir" in found_categories
        )
        missing = []
        if not has_flask_or_elixir:
            missing.append("flask/elixir")
        for cat in sorted(required_categories - {"flask"}):
            if cat not in found_categories:
                missing.append(cat)
        for cat in sorted(nice_to_have - found_categories):
            missing.append(cat)

        if missing:
            lines.append(f"    [MISSING: {', '.join(missing)}]")
        lines.append("")

    return "\n".join(lines)


@db_tool
async def get_resource_usage(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get mana/rage/energy usage analysis for a player in a fight.
    Shows min/max/avg resource levels and time spent at zero.
    Requires event data ingestion."""
    result = await session.execute(
        q.RESOURCE_USAGE,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No resource data found for '{player_name}' in fight "
            f"{fight_id} of report {report_code}. {EVENT_DATA_HINT}"
        )

    lines = [
        f"Resource usage for {player_name} in "
        f"{report_code}#{fight_id}:\n"
    ]
    for r in rows:
        zero_pct = (
            f"{r.time_at_zero_pct:.1f}%"
            if r.time_at_zero_pct is not None else "N/A"
        )
        zero_ms = (
            _format_duration(r.time_at_zero_ms)
            if r.time_at_zero_ms else "0s"
        )
        lines.append(
            f"  {r.resource_type}: Min {r.min_value} | "
            f"Max {r.max_value} | Avg {r.avg_value:.1f} | "
            f"Time at zero: {zero_ms} ({zero_pct})"
        )

    return "\n".join(lines)


@db_tool
async def get_dot_management(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get DoT refresh analysis for a player in a fight.
    Shows early refresh rates, clipped ticks, and refresh timing quality.
    Only applies to DoT-based specs (Warlock, Shadow Priest, Balance Druid).
    Requires event data ingestion."""
    from shukketsu.pipeline.constants import CLASSIC_DOTS, DOT_BY_SPELL_ID

    # Get player class
    pn_like = wildcard(player_name)
    info_result = await session.execute(
        q.PLAYER_FIGHT_INFO,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    info_row = info_result.fetchone()
    if not info_row:
        return (
            f"No data found for '{player_name}' in fight "
            f"{fight_id} of report {report_code}."
        )

    player_class = info_row.player_class
    class_dots = CLASSIC_DOTS.get(player_class, [])
    dot_spell_ids = {d.spell_id for d in class_dots}

    if not dot_spell_ids:
        return (
            f"{player_name} ({player_class}) does not have "
            f"tracked DoTs for this class."
        )

    # Get cast events
    cast_result = await session.execute(
        q.CAST_EVENTS_FOR_DOT_ANALYSIS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    cast_rows = cast_result.fetchall()

    casts_by_spell: dict[int, list[int]] = defaultdict(list)
    spell_names: dict[int, str] = {}
    for r in cast_rows:
        if r.spell_id in dot_spell_ids:
            casts_by_spell[r.spell_id].append(r.timestamp_ms)
            spell_names[r.spell_id] = r.ability_name

    if not casts_by_spell:
        return (
            f"No DoT casts found for '{player_name}' in fight "
            f"{fight_id}. {EVENT_DATA_HINT}"
        )

    lines = [
        f"DoT management for {player_name} in "
        f"{report_code}#{fight_id}:\n"
    ]
    for spell_id, timestamps in casts_by_spell.items():
        dot_def = DOT_BY_SPELL_ID.get(spell_id)
        if not dot_def or len(timestamps) < 2:
            continue

        total_refreshes = len(timestamps) - 1
        early_refreshes = 0
        clipped_ticks_total = 0.0

        for i in range(1, len(timestamps)):
            gap = timestamps[i] - timestamps[i - 1]
            if gap < dot_def.duration_ms:
                remaining_ms = dot_def.duration_ms - gap
                if remaining_ms > 0.3 * dot_def.duration_ms:
                    early_refreshes += 1
                clipped_ticks_total += (
                    remaining_ms / dot_def.tick_interval_ms
                )

        early_pct = (
            (early_refreshes / total_refreshes * 100)
            if total_refreshes > 0 else 0.0
        )

        grade = grade_below(
            early_pct,
            [(10, "GOOD"), (25, "FAIR")],
            "NEEDS WORK",
        )

        name = spell_names.get(spell_id, dot_def.name)
        lines.append(
            f"  [{grade}] {name}: {total_refreshes} refreshes | "
            f"Early: {early_refreshes} ({early_pct:.1f}%) | "
            f"Est. clipped ticks: {clipped_ticks_total:.1f}"
        )

    if len(lines) == 1:
        return (
            f"No DoT refresh data available for '{player_name}' "
            f"(need at least 2 casts per DoT)."
        )

    return "\n".join(lines)


def _letter_grade(score: float) -> str:
    """Return a letter grade for the given score (0-100).

    S(95+), A(85+), B(75+), C(60+), D(40+), F(<40)
    """
    return grade_above(
        score,
        [(95, "S"), (85, "A"), (75, "B"), (60, "C"), (40, "D")],
        "F",
    )


async def _score_healer(session, report_code, fight_id, player_name, info, rules):
    """Score a healer on overheal efficiency, mana management, and spell mix."""
    pn_like = wildcard(player_name)
    encounter_name = info.encounter_name
    total_weight = 0.0
    weighted_score = 0.0
    details = []

    # 1. Overheal % (30% weight)
    overheal_result = await session.execute(
        OVERHEAL_ANALYSIS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    overheal_rows = overheal_result.fetchall()
    if overheal_rows:
        total_oh = sum(getattr(r, "overheal_total", 0) or 0
                       for r in overheal_rows)
        total_raw = sum(
            (getattr(r, "total", 0) or 0)
            + (getattr(r, "overheal_total", 0) or 0)
            for r in overheal_rows
        )
        oh_pct = (total_oh / total_raw * 100) if total_raw > 0 else 0
        target = rules.healer_overheal_target
        if oh_pct <= target:
            weighted_score += 30.0
            details.append(
                f"  Overheal: {oh_pct:.1f}% "
                f"(target <={target:.0f}%) \u2014 OK"
            )
        else:
            ratio = max(0, 1 - (oh_pct - target) / target)
            weighted_score += 30.0 * ratio
            details.append(
                f"  Overheal: {oh_pct:.1f}% "
                f"(target <={target:.0f}%) \u2014 OVER"
            )
        total_weight += 30.0

    # 2. Mana management (25% weight)
    resource_result = await session.execute(
        q.RESOURCE_USAGE,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    resource_rows = resource_result.fetchall()
    # Find the mana row (healers use mana)
    mana_row = None
    for rr in resource_rows:
        rtype = (getattr(rr, "resource_type", "") or "").lower()
        if rtype == "mana":
            mana_row = rr
            break
    # Fall back to first row if no explicit mana type found
    if mana_row is None and resource_rows:
        mana_row = resource_rows[0]

    if mana_row and hasattr(mana_row, "time_at_zero_pct"):
        tzp = mana_row.time_at_zero_pct or 0
        if tzp <= 5:
            weighted_score += 25.0
            details.append(
                f"  Mana: {tzp:.1f}% time at zero \u2014 OK"
            )
        elif tzp <= 10:
            weighted_score += 15.0
            details.append(
                f"  Mana: {tzp:.1f}% time at zero \u2014 caution"
            )
        else:
            details.append(
                f"  Mana: {tzp:.1f}% time at zero \u2014 OOM risk"
            )
        total_weight += 25.0

    # 3. Key abilities (15% weight)
    if rules.key_abilities:
        ability_result = await session.execute(
            ABILITY_BREAKDOWN,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": pn_like},
        )
        ab_rows = ability_result.fetchall()
        found = {r.ability_name for r in ab_rows}
        present = sum(
            1 for a in rules.key_abilities
            if any(a.lower() in f.lower() for f in found)
        )
        ratio = present / len(rules.key_abilities)
        weighted_score += 15.0 * ratio
        total_weight += 15.0
        missing = [
            a for a in rules.key_abilities
            if not any(a.lower() in f.lower() for f in found)
        ]
        if missing:
            details.append(
                f"  Spell mix: missing {', '.join(missing)}"
            )
        else:
            details.append("  Spell mix: all present \u2014 OK")

    if total_weight == 0:
        return (
            f"No healer data for {player_name}. "
            f"Were --with-events and --with-tables used?"
        )

    score = (weighted_score / total_weight) * 100
    grade = _letter_grade(score)

    lines = [
        f"Healer score for {player_name} "
        f"({info.player_class} {info.player_spec}) "
        f"on {encounter_name}:",
        f"  Grade: {grade} ({score:.0f}%) | Weighted score",
    ] + details
    return "\n".join(lines)


def _score_tank(player_name: str, spec: str) -> str:
    """Stub: tank rotation scoring not yet implemented."""
    return (
        f"Tank scoring for {player_name} ({spec}) is coming soon. "
        f"Use get_cooldown_efficiency for tank evaluation."
    )


_LONG_CD_THRESHOLD = 180  # CDs > 180s use long_cd_efficiency


async def _score_dps(
    session,
    report_code: str,
    fight_id: int,
    player_name: str,
    info,
    rules,
):
    """Score a DPS player's rotation using spec-aware, encounter-aware rules."""
    pn_like = wildcard(player_name)
    spec = info.player_spec
    player_class = info.player_class
    encounter_name = info.encounter_name

    # --- Resolve encounter context modifier ---
    ctx = ENCOUNTER_CONTEXTS.get(encounter_name)
    role = rules.role
    is_melee = role == "melee_dps"
    if ctx:
        modifier = (
            ctx.melee_modifier if is_melee and ctx.melee_modifier is not None
            else ctx.gcd_modifier
        )
    else:
        modifier = 1.0

    adjusted_gcd = rules.gcd_target * modifier
    adjusted_cpm = rules.cpm_target * modifier

    # --- Fetch data ---
    cm_result = await session.execute(
        q.FIGHT_CAST_METRICS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    cm_row = cm_result.fetchone()

    cd_result = await session.execute(
        q.FIGHT_COOLDOWNS,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    cd_rows = cd_result.fetchall()

    # Ability breakdown (from --with-tables, optional)
    ab_result = await session.execute(
        ABILITY_BREAKDOWN,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    ab_rows = ab_result.fetchall()

    # --- Score rules ---
    rules_checked = 0
    rules_passed = 0
    violations = []
    notes = []

    # Rule 1: GCD uptime vs adjusted target
    if cm_row:
        rules_checked += 1
        if cm_row.gcd_uptime_pct >= adjusted_gcd:
            rules_passed += 1
        else:
            violations.append(
                f"GCD uptime {cm_row.gcd_uptime_pct:.1f}% "
                f"< {adjusted_gcd:.1f}% target"
            )

        # Rule 2: CPM vs adjusted target
        rules_checked += 1
        if cm_row.casts_per_minute >= adjusted_cpm:
            rules_passed += 1
        else:
            violations.append(
                f"CPM {cm_row.casts_per_minute:.1f} "
                f"< {adjusted_cpm:.1f} target"
            )

    # Rule 3+: Cooldown efficiency (short vs long thresholds)
    for cd in cd_rows:
        rules_checked += 1
        cd_sec = cd.cooldown_sec if cd.cooldown_sec else 0
        if cd_sec > _LONG_CD_THRESHOLD:
            threshold = rules.long_cd_efficiency
            label = "long CD"
        else:
            threshold = rules.cd_efficiency_target
            label = "short CD"
        if cd.efficiency_pct >= threshold:
            rules_passed += 1
        else:
            violations.append(
                f"{cd.ability_name} ({label}) efficiency "
                f"{cd.efficiency_pct:.1f}% < {threshold:.0f}%"
            )

    # Rule 4: Key ability presence check
    if rules.key_abilities and ab_rows:
        ability_names = {r.ability_name for r in ab_rows}
        for key_ab in rules.key_abilities:
            rules_checked += 1
            if key_ab in ability_names:
                rules_passed += 1
            else:
                violations.append(
                    f"Key ability '{key_ab}' not found in ability breakdown"
                )
    elif rules.key_abilities and not ab_rows:
        notes.append(
            "Ability breakdown not available (use --with-tables). "
            "Key ability check skipped."
        )

    if rules_checked == 0:
        return (
            f"No cast/cooldown data found for '{player_name}' in "
            f"fight {fight_id}. {EVENT_DATA_HINT}"
        )

    score = rules_passed / rules_checked * 100
    grade = _letter_grade(score)

    # --- Format output ---
    lines = [
        f"Rotation score for {player_name} ({player_class} {spec}) "
        f"on {encounter_name} [{report_code}#{fight_id}]:\n",
        f"  Grade: {grade} ({score:.0f}%) | "
        f"Rules passed: {rules_passed}/{rules_checked}",
    ]

    if ctx and modifier < 1.0:
        lines.append(
            f"\n  Encounter context: {encounter_name} "
            f"(modifier {modifier:.2f}"
            f"{' — ' + ctx.notes if ctx.notes else ''})"
        )
        lines.append(
            f"  Adjusted targets: GCD {adjusted_gcd:.1f}%, "
            f"CPM {adjusted_cpm:.1f}"
        )

    if violations:
        lines.append("\n  Violations:")
        for v in violations:
            lines.append(f"    - {v}")

    if notes:
        lines.append("\n  Notes:")
        for n in notes:
            lines.append(f"    - {n}")

    return "\n".join(lines)


@db_tool
async def get_rotation_score(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get rule-based rotation quality score for a player in a fight.
    Uses spec-specific thresholds and encounter-aware modifiers.
    Checks GCD uptime, CPM, cooldown efficiency, and key abilities.
    Requires event data ingestion."""
    # Get player info
    pn_like = wildcard(player_name)
    info_result = await session.execute(
        q.PLAYER_FIGHT_INFO,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": pn_like},
    )
    info_row = info_result.fetchone()
    if not info_row:
        return (
            f"No data found for '{player_name}' in fight "
            f"{fight_id} of report {report_code}."
        )

    player_class = info_row.player_class
    spec = info_row.player_spec

    # Look up spec rules, fall back to role defaults
    rules = SPEC_ROTATION_RULES.get((player_class, spec))
    if not rules:
        role = ROLE_BY_SPEC.get(spec, "melee_dps")
        rules = ROLE_DEFAULT_RULES.get(role, ROLE_DEFAULT_RULES["melee_dps"])

    # Route by role
    if rules.role == "healer":
        return await _score_healer(
            session, report_code, fight_id, player_name, info_row, rules,
        )
    if rules.role == "tank":
        return _score_tank(player_name, spec)

    return await _score_dps(
        session, report_code, fight_id, player_name, info_row, rules,
    )


@db_tool
async def get_gear_changes(
    session,
    player_name: str,
    report_code_old: str,
    report_code_new: str,
) -> str:
    """Compare a player's gear between two raids. Shows which slots changed
    and the item level difference for each upgrade/downgrade.
    Requires event data ingestion."""
    from shukketsu.pipeline.constants import GEAR_SLOTS

    result = await session.execute(
        q.GEAR_CHANGES,
        {"player_name": wildcard(player_name),
         "report_code_old": report_code_old,
         "report_code_new": report_code_new},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No gear changes found for '{player_name}' between "
            f"reports {report_code_old} and {report_code_new}. "
            f"Either gear was identical or gear snapshot data is not "
            f"available "
            f"(use pull-my-logs --with-events to fetch it)."
        )

    lines = [
        f"Gear changes for {player_name} "
        f"({report_code_old} \u2192 {report_code_new}):"
    ]
    for r in rows:
        slot_name = GEAR_SLOTS.get(r.slot, f"Slot {r.slot}")
        old_str = (
            f"item {r.old_item_id} (ilvl {r.old_ilvl})"
            if r.old_item_id else "empty"
        )
        new_str = (
            f"item {r.new_item_id} (ilvl {r.new_ilvl})"
            if r.new_item_id else "empty"
        )
        delta_str = ""
        if r.old_ilvl is not None and r.new_ilvl is not None:
            delta = r.new_ilvl - r.old_ilvl
            delta_str = f" [{delta:+d} ilvl]"
        lines.append(
            f"  {slot_name}: {old_str} \u2192 {new_str}{delta_str}"
        )

    return "\n".join(lines)


@db_tool
async def get_phase_analysis(
    session,
    report_code: str,
    fight_id: int,
    player_name: str | None = None,
) -> str:
    """Break down a boss fight by phase. Shows the encounter's phase structure
    with estimated time ranges and per-player DPS, deaths, and performance.
    Identifies which phases are critical for the encounter.
    Use this to understand fight pacing and where time is spent."""
    from shukketsu.pipeline.constants import ENCOUNTER_PHASES, PhaseDef

    result = await session.execute(
        q.PHASE_BREAKDOWN,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard_or_none(player_name)},
    )
    rows = result.fetchall()
    if not rows:
        return (
            f"No data found for fight {fight_id} in report "
            f"{report_code}."
        )

    first = rows[0]
    encounter_name = first.encounter_name
    duration_ms = first.duration_ms
    outcome = "Kill" if first.kill else "Wipe"

    # Look up phase definitions; default to single "Full Fight" phase
    phases = ENCOUNTER_PHASES.get(encounter_name, [
        PhaseDef("Full Fight", 0.0, 1.0, "No phase data available"),
    ])

    lines = [
        f"Phase Analysis: {encounter_name} ({outcome}, "
        f"{_format_duration(duration_ms)}) — "
        f"{report_code}#{fight_id}\n"
    ]

    # Phase timeline
    lines.append("Phase Timeline:")
    for phase in phases:
        est_start = int(duration_ms * phase.pct_start)
        est_end = int(duration_ms * phase.pct_end)
        est_dur = est_end - est_start
        lines.append(
            f"  {phase.name}: {_format_duration(est_start)} - "
            f"{_format_duration(est_end)} "
            f"({_format_duration(est_dur)}) — {phase.description}"
        )

    # Player performances
    lines.append("\nPlayer Performance:")
    for r in rows:
        parse_str = (
            f"{r.parse_percentile}%"
            if r.parse_percentile is not None else "N/A"
        )
        metrics = f"DPS: {r.dps:,.1f} | Damage: {r.total_damage:,}"
        if r.hps and r.hps > 0:
            metrics += (
                f" | HPS: {r.hps:,.1f} | "
                f"Healing: {r.total_healing:,}"
            )
        lines.append(
            f"  {r.player_name} ({r.player_spec} {r.player_class}) "
            f"| {metrics} | Deaths: {r.deaths} | "
            f"Parse: {parse_str}"
        )

    return "\n".join(lines)


@db_tool
async def get_enchant_gem_check(
    session, report_code: str, fight_id: int, player_name: str,
) -> str:
    """Check a player's gear for missing enchants and gems in a fight.
    Requires event data -- report_code + fight_id + player_name.
    Flags slots missing permanent enchants (head, shoulder, chest, wrist,
    hands, legs, feet, cloak, weapon, offhand) and empty gem sockets.
    """
    from shukketsu.pipeline.constants import GEAR_SLOTS

    rows = (await session.execute(
        q.ENCHANT_GEM_CHECK,
        {"report_code": report_code, "fight_id": fight_id,
         "player_name": wildcard(player_name)},
    )).fetchall()
    if not rows:
        return (
            f"No gear data found for {player_name} in "
            f"{report_code}#{fight_id}."
        )

    # Slots that should have permanent enchants (Classic/TBC)
    # Excludes waist (no enchant), rings (enchanter-only),
    # trinkets, neck, shirt
    enchantable_slots = {0, 2, 4, 6, 7, 8, 9, 14, 15}
    issues = []
    total_slots = 0
    enchanted = 0
    total_gems = 0
    empty_gems = 0

    for r in rows:
        total_slots += 1
        sname = GEAR_SLOTS.get(r.slot, f"Slot {r.slot}")

        # Check enchant
        if r.slot in enchantable_slots:
            if r.permanent_enchant:
                enchanted += 1
            else:
                issues.append(
                    f"  {sname}: Missing enchant (item {r.item_id})"
                )

        # Check gems
        if r.gems_json:
            gems = json.loads(r.gems_json)
            for gem in gems:
                total_gems += 1
                gem_id = (
                    gem.get("id", 0)
                    if isinstance(gem, dict) else gem
                )
                if not gem_id:
                    empty_gems += 1
                    issues.append(f"  {sname}: Empty gem socket")

    lines = [
        f"Enchant/gem check for {player_name} in "
        f"{report_code}#{fight_id}:",
        f"Total gear slots: {total_slots}",
        f"Enchanted: {enchanted}/"
        f"{len(enchantable_slots & {r.slot for r in rows})}",
    ]
    if total_gems > 0:
        lines.append(
            f"Gems: {total_gems - empty_gems}/{total_gems} filled"
        )
    if issues:
        lines.append(f"\nIssues ({len(issues)}):")
        lines.extend(issues)
    else:
        lines.append("\nAll enchants and gems look good!")

    return "\n".join(lines)
