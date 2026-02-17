"""Pipeline for ingesting WCL events data (deaths, cast metrics, cooldowns)."""

import json
import logging

from sqlalchemy import delete, select

from shukketsu.db.models import (
    CancelledCast,
    CastEvent,
    CastMetric,
    CooldownUsage,
    CooldownWindow,
    DeathDetail,
    DotRefresh,
    Fight,
    FightPerformance,
    PhaseMetric,
    ResourceSnapshot,
    RotationScore,
)

logger = logging.getLogger(__name__)

# --- Cast metrics constants ---
GCD_MS = 1500  # Classic baseline GCD
GAP_THRESHOLD_MS = 2500  # Gaps longer than this are "significant"


# ===== Death event parsing =====

def parse_death_events(
    events: list[dict],
    fight_start_time: int,
    actor_name_by_id: dict[int, str],
) -> list[DeathDetail]:
    """Parse WCL Deaths events into DeathDetail rows.

    WCL Deaths events have structure:
      {"timestamp": int, "sourceID": int (who died),
       "killingAbility": {"name": str} | None,
       "killerID": int | None,
       "events": [{"timestamp": int, "type": str, "amount": int,
                    "ability": {"name": str}, "sourceID": int, ...}]}
    """
    # Track death count per player for death_index
    death_counts: dict[str, int] = {}
    results: list[DeathDetail] = []

    for event in events:
        source_id = event.get("sourceID")
        player_name = actor_name_by_id.get(source_id, f"Unknown-{source_id}")

        death_counts[player_name] = death_counts.get(player_name, 0) + 1
        death_index = death_counts[player_name]

        timestamp_ms = event.get("timestamp", 0) - fight_start_time

        # Killing blow info
        killing_ability = event.get("killingAbility") or {}
        killing_blow_ability = killing_ability.get("name", "Unknown")

        killer_id = event.get("killerID")
        killing_blow_source = actor_name_by_id.get(killer_id, "Environment")

        # Pre-death damage events (last 10)
        sub_events = event.get("events", [])
        damage_events = [
            e for e in sub_events
            if e.get("type") in ("damage", "absorbed")
        ]
        last_events = damage_events[-10:]

        damage_taken_total = sum(e.get("amount", 0) for e in damage_events)

        # Compact JSON for the event timeline
        events_compact = []
        for e in last_events:
            ability = e.get("ability") or {}
            e_source_id = e.get("sourceID")
            events_compact.append({
                "ts": e.get("timestamp", 0) - fight_start_time,
                "ability": ability.get("name", "Unknown"),
                "amount": e.get("amount", 0),
                "source": actor_name_by_id.get(e_source_id, f"NPC-{e_source_id}"),
                "type": e.get("type", "damage"),
            })

        results.append(DeathDetail(
            player_name=player_name,
            death_index=death_index,
            timestamp_ms=timestamp_ms,
            killing_blow_ability=killing_blow_ability,
            killing_blow_source=killing_blow_source,
            damage_taken_total=damage_taken_total,
            events_json=json.dumps(events_compact),
        ))

    return results


async def ingest_deaths_for_fight(
    wcl, session, report_code: str, fight: Fight,
    actor_name_by_id: dict[int, str],
) -> int:
    """Fetch and ingest death events for a single fight. Returns rows inserted."""
    from shukketsu.wcl.events import fetch_all_events

    # Delete existing death details for this fight (idempotent)
    await session.execute(
        delete(DeathDetail).where(DeathDetail.fight_id == fight.id)
    )

    try:
        events = await fetch_all_events(
            wcl, report_code, fight.start_time, fight.end_time, "Deaths",
        )
    except Exception:
        logger.exception(
            "Failed to fetch Deaths events for fight %d in %s",
            fight.fight_id, report_code,
        )
        return 0

    if not events:
        return 0

    details = parse_death_events(events, fight.start_time, actor_name_by_id)
    for d in details:
        d.fight_id = fight.id
        session.add(d)

    logger.info(
        "Ingested %d death details for fight %d (%s)",
        len(details), fight.fight_id, report_code,
    )
    return len(details)


# ===== Cast metrics computation =====

def compute_cast_metrics(
    cast_events: list[dict],
    fight_duration_ms: int,
) -> dict:
    """Compute GCD uptime / ABC metrics from a sorted list of cast events.

    Args:
        cast_events: Sorted list of {"timestamp": int, ...} events.
        fight_duration_ms: Total fight duration in milliseconds.

    Returns:
        Dict with: total_casts, casts_per_minute, gcd_uptime_pct,
        active_time_ms, downtime_ms, longest_gap_ms, longest_gap_at_ms,
        avg_gap_ms, gap_count.
    """
    total_casts = len(cast_events)
    if total_casts == 0 or fight_duration_ms <= 0:
        return {
            "total_casts": total_casts,
            "casts_per_minute": 0.0,
            "gcd_uptime_pct": 0.0,
            "active_time_ms": 0,
            "downtime_ms": fight_duration_ms if fight_duration_ms > 0 else 0,
            "longest_gap_ms": fight_duration_ms if fight_duration_ms > 0 else 0,
            "longest_gap_at_ms": 0,
            "avg_gap_ms": 0.0,
            "gap_count": 0,
        }

    timestamps = sorted(e["timestamp"] for e in cast_events)
    fight_minutes = fight_duration_ms / 60_000
    casts_per_minute = round(total_casts / fight_minutes, 1) if fight_minutes > 0 else 0.0

    # Walk timestamps, sum active time (each cast = 1 GCD of active time)
    active_time_ms = total_casts * GCD_MS
    # Cap active time at fight duration
    if active_time_ms > fight_duration_ms:
        active_time_ms = fight_duration_ms

    # Track gaps between casts
    significant_gaps: list[dict] = []
    longest_gap_ms = 0
    longest_gap_at_ms = 0

    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        if gap > longest_gap_ms:
            longest_gap_ms = gap
            longest_gap_at_ms = timestamps[i - 1] - timestamps[0]
        if gap > GAP_THRESHOLD_MS:
            significant_gaps.append({"gap_ms": gap, "at_ms": timestamps[i - 1] - timestamps[0]})

    gap_count = len(significant_gaps)
    avg_gap_ms = (
        round(sum(g["gap_ms"] for g in significant_gaps) / gap_count, 1)
        if gap_count > 0 else 0.0
    )

    downtime_ms = fight_duration_ms - active_time_ms
    if downtime_ms < 0:
        downtime_ms = 0

    gcd_uptime_pct = round(active_time_ms / fight_duration_ms * 100, 1)

    return {
        "total_casts": total_casts,
        "casts_per_minute": casts_per_minute,
        "gcd_uptime_pct": gcd_uptime_pct,
        "active_time_ms": active_time_ms,
        "downtime_ms": downtime_ms,
        "longest_gap_ms": longest_gap_ms,
        "longest_gap_at_ms": longest_gap_at_ms,
        "avg_gap_ms": avg_gap_ms,
        "gap_count": gap_count,
    }


async def ingest_casts_for_fight(
    session, fight: Fight, cast_events: list[dict],
    actor_name_by_id: dict[int, str], fight_duration_ms: int,
) -> int:
    """Compute and store cast metrics for all players in a fight.

    Args:
        session: DB session.
        fight: Fight ORM object.
        cast_events: All Casts events for this fight (all players).
        actor_name_by_id: actor ID → name mapping.
        fight_duration_ms: Total fight duration.

    Returns:
        Number of CastMetric rows inserted.
    """
    # Delete existing cast metrics for this fight
    await session.execute(
        delete(CastMetric).where(CastMetric.fight_id == fight.id)
    )

    if not cast_events:
        return 0

    # Group by sourceID
    events_by_source: dict[int, list[dict]] = {}
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is not None:
            events_by_source.setdefault(sid, []).append(event)

    total_rows = 0
    for source_id, player_events in events_by_source.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue

        metrics = compute_cast_metrics(player_events, fight_duration_ms)
        session.add(CastMetric(
            fight_id=fight.id,
            player_name=player_name,
            **metrics,
        ))
        total_rows += 1

    logger.info(
        "Ingested cast metrics for %d players in fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Cooldown tracking =====

def compute_cooldown_usage(
    cast_events: list[dict],
    player_class: str,
    fight_duration_ms: int,
) -> list[dict]:
    """Compute cooldown usage efficiency from cast events for a single player.

    Args:
        cast_events: Sorted Casts events for one player.
        player_class: WoW class name (e.g. "Warrior").
        fight_duration_ms: Total fight duration.

    Returns:
        List of dicts, one per known cooldown spell, with usage stats.
    """
    from shukketsu.pipeline.constants import CLASSIC_COOLDOWNS

    cooldown_defs = CLASSIC_COOLDOWNS.get(player_class, [])
    if not cooldown_defs:
        return []

    # Build set of known cooldown spell IDs for fast lookup
    cd_by_spell_id = {cd.spell_id: cd for cd in cooldown_defs}

    # Group casts by spell ID (only cooldown spells)
    casts_by_spell: dict[int, list[int]] = {}
    for event in cast_events:
        # WCL Casts events have abilityGameID as a top-level int
        spell_id = event.get("abilityGameID", 0)
        if spell_id in cd_by_spell_id:
            ts = event.get("timestamp", 0)
            casts_by_spell.setdefault(spell_id, []).append(ts)

    results = []
    for cd in cooldown_defs:
        timestamps = sorted(casts_by_spell.get(cd.spell_id, []))
        times_used = len(timestamps)

        # max_possible: floor(duration_sec / cooldown_sec) + 1
        fight_sec = fight_duration_ms / 1000
        max_possible = int(fight_sec // cd.cooldown_sec) + 1 if fight_sec > 0 else 1

        efficiency_pct = round(times_used / max_possible * 100, 1) if max_possible > 0 else 0.0
        if efficiency_pct > 100:
            efficiency_pct = 100.0

        first_use_ms = timestamps[0] if timestamps else None
        last_use_ms = timestamps[-1] if timestamps else None

        results.append({
            "spell_id": cd.spell_id,
            "ability_name": cd.name,
            "cooldown_sec": cd.cooldown_sec,
            "times_used": times_used,
            "max_possible_uses": max_possible,
            "first_use_ms": first_use_ms,
            "last_use_ms": last_use_ms,
            "efficiency_pct": efficiency_pct,
        })

    return results


async def ingest_cooldowns_for_fight(
    session, fight: Fight, cast_events: list[dict],
    actor_name_by_id: dict[int, str], fight_duration_ms: int,
) -> int:
    """Compute and store cooldown usage for all players in a fight.

    Requires player class lookup from fight_performances.
    """
    # Delete existing cooldown usage for this fight
    await session.execute(
        delete(CooldownUsage).where(CooldownUsage.fight_id == fight.id)
    )

    if not cast_events:
        return 0

    # Get player classes from fight_performances
    result = await session.execute(
        select(FightPerformance.player_name, FightPerformance.player_class)
        .where(FightPerformance.fight_id == fight.id)
    )
    player_classes = {r.player_name: r.player_class for r in result}

    # Group cast events by sourceID
    events_by_source: dict[int, list[dict]] = {}
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is not None:
            events_by_source.setdefault(sid, []).append(event)

    total_rows = 0
    for source_id, player_events in events_by_source.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue

        player_class = player_classes.get(player_name)
        if not player_class:
            continue

        cd_usage = compute_cooldown_usage(player_events, player_class, fight_duration_ms)
        for cd in cd_usage:
            session.add(CooldownUsage(
                fight_id=fight.id,
                player_name=player_name,
                **cd,
            ))
            total_rows += 1

    logger.info(
        "Ingested %d cooldown usage rows for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Cancelled cast detection =====

def compute_cancelled_casts(cast_events: list[dict]) -> dict[str, dict]:
    """Compute cancelled casts per player from Casts events.

    WCL Casts events have type "begincast" (start casting) and "cast" (success).
    A begincast without a matching cast = cancelled.

    Returns:
        Dict[player_name -> {total_begins, total_completions, cancel_count,
                             cancel_pct, top_cancelled}]
    """
    # Track begincast/cast per player per spell
    # Key: (sourceID, abilityGameID) -> list of {type, timestamp}
    player_begins: dict[int, int] = {}
    player_completions: dict[int, int] = {}
    player_cancel_by_spell: dict[int, dict[int, int]] = {}

    for event in cast_events:
        sid = event.get("sourceID")
        if sid is None:
            continue

        event_type = event.get("type", "")
        spell_id = event.get("abilityGameID", 0)

        if event_type == "begincast":
            player_begins[sid] = player_begins.get(sid, 0) + 1
        elif event_type == "cast":
            player_completions[sid] = player_completions.get(sid, 0) + 1

        # Track per-spell cancels by matching begincast to casts
        # Simpler approach: count begincast - cast per spell per player
        if event_type == "begincast":
            player_cancel_by_spell.setdefault(sid, {}).setdefault(spell_id, 0)
            player_cancel_by_spell[sid][spell_id] += 1
        elif event_type == "cast" and sid in player_cancel_by_spell:
            if spell_id in player_cancel_by_spell[sid]:
                player_cancel_by_spell[sid][spell_id] -= 1

    results = {}
    all_sources = set(player_begins.keys()) | set(player_completions.keys())

    for sid in all_sources:
        begins = player_begins.get(sid, 0)
        completions = player_completions.get(sid, 0)
        cancels = max(0, begins - completions)
        cancel_pct = round(cancels / begins * 100, 1) if begins > 0 else 0.0

        # Get top cancelled spells
        spell_cancels = player_cancel_by_spell.get(sid, {})
        top_cancelled = sorted(
            [(spell_id, count) for spell_id, count in spell_cancels.items() if count > 0],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        results[sid] = {
            "total_begins": begins,
            "total_completions": completions,
            "cancel_count": cancels,
            "cancel_pct": cancel_pct,
            "top_cancelled": top_cancelled,
        }

    return results


async def ingest_cancelled_casts_for_fight(
    session, fight: Fight, cast_events: list[dict],
    actor_name_by_id: dict[int, str],
) -> int:
    """Compute and store cancelled cast metrics for all players in a fight."""
    await session.execute(
        delete(CancelledCast).where(CancelledCast.fight_id == fight.id)
    )

    if not cast_events:
        return 0

    cancelled_data = compute_cancelled_casts(cast_events)

    total_rows = 0
    for source_id, data in cancelled_data.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue
        if data["total_begins"] == 0:
            continue

        # Build top cancelled JSON with spell names
        top_json = json.dumps([
            {"spell_id": spell_id, "count": count}
            for spell_id, count in data["top_cancelled"]
        ]) if data["top_cancelled"] else None

        session.add(CancelledCast(
            fight_id=fight.id,
            player_name=player_name,
            total_begins=data["total_begins"],
            total_completions=data["total_completions"],
            cancel_count=data["cancel_count"],
            cancel_pct=data["cancel_pct"],
            top_cancelled_json=top_json,
        ))
        total_rows += 1

    logger.info(
        "Ingested %d cancelled cast rows for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Cast event storage (for timeline) =====

async def ingest_cast_events_for_fight(
    session, fight: Fight, cast_events: list[dict],
    actor_name_by_id: dict[int, str],
) -> int:
    """Store individual cast events for timeline visualization."""
    await session.execute(
        delete(CastEvent).where(CastEvent.fight_id == fight.id)
    )

    if not cast_events:
        return 0

    total_rows = 0
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is None:
            continue
        player_name = actor_name_by_id.get(sid)
        if not player_name:
            continue

        event_type = event.get("type", "cast")
        if event_type not in ("cast", "begincast"):
            continue

        spell_id = event.get("abilityGameID", 0)
        ability_info = event.get("ability") or {}
        ability_name = ability_info.get(
            "name", f"Spell-{spell_id}"
        )
        timestamp_ms = event.get("timestamp", 0) - fight.start_time
        target_id = event.get("targetID")
        target_name = (
            actor_name_by_id.get(target_id) if target_id else None
        )

        session.add(CastEvent(
            fight_id=fight.id,
            player_name=player_name,
            timestamp_ms=timestamp_ms,
            spell_id=spell_id,
            ability_name=ability_name,
            event_type=event_type,
            target_name=target_name,
        ))
        total_rows += 1

    logger.info(
        "Ingested %d cast events for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Resource tracking =====

# WCL resource type IDs
RESOURCE_TYPE_NAMES = {
    0: "mana",
    1: "rage",
    2: "focus",
    3: "energy",
}


def compute_resource_metrics(
    resource_events: list[dict],
    fight_duration_ms: int,
    fight_start_time: int = 0,
) -> dict[tuple[int, int], dict]:
    """Compute resource metrics per player from WCL resource change events.

    WCL resource events have:
      sourceID, timestamp, resourceActor,
      classResources: [{amount, max, type}]

    Returns dict[(sourceID, resource_type_int) -> {resource_type, min_value,
        max_value, avg_value, time_at_zero_ms, time_at_zero_pct, samples}]
    """
    # Group by (sourceID, resource_type)
    player_resources: dict[
        tuple[int, int], list[tuple[int, int, int]]
    ] = {}

    for event in resource_events:
        sid = event.get("sourceID")
        if sid is None:
            continue
        ts = event.get("timestamp", 0) - fight_start_time
        class_resources = event.get("classResources", [])
        for cr in class_resources:
            rtype = cr.get("type", -1)
            if rtype not in RESOURCE_TYPE_NAMES:
                continue
            amount = cr.get("amount", 0)
            max_val = cr.get("max", 0)
            player_resources.setdefault(
                (sid, rtype), [],
            ).append((ts, amount, max_val))

    results: dict[tuple[int, int], dict] = {}
    for (sid, rtype), entries in player_resources.items():
        entries.sort(key=lambda x: x[0])
        amounts = [e[1] for e in entries]
        max_vals = [e[2] for e in entries]

        min_val = min(amounts) if amounts else 0
        max_val = max(max_vals) if max_vals else 0
        avg_val = (
            round(sum(amounts) / len(amounts), 1) if amounts else 0.0
        )

        # Time at zero: estimate from consecutive events
        time_at_zero = 0
        for i in range(len(entries) - 1):
            if entries[i][1] == 0:
                gap = entries[i + 1][0] - entries[i][0]
                time_at_zero += gap

        time_at_zero_pct = (
            round(time_at_zero / fight_duration_ms * 100, 1)
            if fight_duration_ms > 0 else 0.0
        )

        # Downsample to ~60 points max for chart
        sample_interval = max(1, len(entries) // 60)
        samples = []
        for i in range(0, len(entries), sample_interval):
            ts_offset = entries[i][0]
            samples.append({
                "t": ts_offset,
                "v": entries[i][1],
            })

        results[(sid, rtype)] = {
            "resource_type": RESOURCE_TYPE_NAMES[rtype],
            "min_value": min_val,
            "max_value": max_val,
            "avg_value": avg_val,
            "time_at_zero_ms": time_at_zero,
            "time_at_zero_pct": time_at_zero_pct,
            "samples": samples,
        }

    return results


async def ingest_resources_for_fight(
    wcl, session, report_code: str, fight: Fight,
    actor_name_by_id: dict[int, str],
) -> int:
    """Fetch and ingest resource data for a fight."""
    from shukketsu.wcl.events import fetch_all_events

    await session.execute(
        delete(ResourceSnapshot).where(
            ResourceSnapshot.fight_id == fight.id,
        )
    )

    fight_duration_ms = fight.end_time - fight.start_time

    try:
        events = await fetch_all_events(
            wcl, report_code,
            fight.start_time, fight.end_time, "Resources",
        )
    except Exception:
        logger.exception(
            "Failed to fetch Resources for fight %d in %s",
            fight.fight_id, report_code,
        )
        return 0

    if not events:
        return 0

    metrics = compute_resource_metrics(events, fight_duration_ms, fight.start_time)

    total_rows = 0
    for (sid, _rtype), data in metrics.items():
        player_name = actor_name_by_id.get(sid)
        if not player_name:
            continue

        session.add(ResourceSnapshot(
            fight_id=fight.id,
            player_name=player_name,
            resource_type=data["resource_type"],
            min_value=data["min_value"],
            max_value=data["max_value"],
            avg_value=data["avg_value"],
            time_at_zero_ms=data["time_at_zero_ms"],
            time_at_zero_pct=data["time_at_zero_pct"],
            samples_json=json.dumps(data["samples"]),
        ))
        total_rows += 1

    logger.info(
        "Ingested %d resource snapshots for fight %d (%s)",
        total_rows, fight.fight_id, report_code,
    )
    return total_rows


# ===== Cooldown window throughput =====

def compute_cooldown_windows(
    cast_events: list[dict],
    damage_events: list[dict],
    player_class: str,
    fight_duration_ms: int,
    fight_start_time: int,
) -> list[dict]:
    """Compute DPS during cooldown windows vs baseline.

    For each major cooldown activation, calculate damage done during
    the window vs baseline DPS outside all windows.
    """
    from shukketsu.pipeline.constants import CLASSIC_COOLDOWNS

    cooldown_defs = CLASSIC_COOLDOWNS.get(player_class, [])
    if not cooldown_defs:
        return []

    cd_by_spell_id = {cd.spell_id: cd for cd in cooldown_defs}

    # Find cooldown activation timestamps
    activations: list[dict] = []
    for event in cast_events:
        spell_id = event.get("abilityGameID", 0)
        if spell_id in cd_by_spell_id:
            cd = cd_by_spell_id[spell_id]
            ts = event.get("timestamp", 0) - fight_start_time
            # Use actual buff duration if known, fall back to cooldown
            buff_dur = cd.duration_sec if cd.duration_sec > 0 else cd.cooldown_sec
            activations.append({
                "spell_id": spell_id,
                "ability_name": cd.name,
                "start_ms": ts,
                "end_ms": ts + buff_dur * 1000,
                "duration_sec": buff_dur,
            })

    if not activations:
        return []

    # Calculate total damage across the fight
    total_fight_damage = 0
    for dmg in damage_events:
        total_fight_damage += dmg.get("amount", 0)

    results = []
    total_cd_time_ms = 0
    total_cd_damage = 0

    for act in activations:
        window_damage = 0
        for dmg in damage_events:
            ts = dmg.get("timestamp", 0) - fight_start_time
            if act["start_ms"] <= ts <= act["end_ms"]:
                window_damage += dmg.get("amount", 0)

        window_ms = act["end_ms"] - act["start_ms"]
        if window_ms > fight_duration_ms:
            window_ms = fight_duration_ms
        window_dps = (
            round(window_damage / (window_ms / 1000), 1)
            if window_ms > 0 else 0.0
        )

        total_cd_time_ms += window_ms
        total_cd_damage += window_damage

        results.append({
            "ability_name": act["ability_name"],
            "spell_id": act["spell_id"],
            "window_start_ms": act["start_ms"],
            "window_end_ms": act["end_ms"],
            "window_damage": window_damage,
            "window_dps": window_dps,
            "baseline_dps": 0.0,  # filled below
            "dps_gain_pct": 0.0,
        })

    # Baseline = damage outside all CD windows / non-CD time
    non_cd_time_ms = fight_duration_ms - total_cd_time_ms
    non_cd_damage = total_fight_damage - total_cd_damage
    baseline_dps = (
        round(non_cd_damage / (non_cd_time_ms / 1000), 1)
        if non_cd_time_ms > 0 else 0.0
    )

    for r in results:
        r["baseline_dps"] = baseline_dps
        if baseline_dps > 0:
            r["dps_gain_pct"] = round(
                (r["window_dps"] - baseline_dps) / baseline_dps * 100,
                1,
            )

    return results


async def ingest_cooldown_windows_for_fight(
    session, fight: Fight,
    cast_events: list[dict],
    damage_events: list[dict],
    actor_name_by_id: dict[int, str],
) -> int:
    """Compute and store cooldown window throughput for all players."""
    await session.execute(
        delete(CooldownWindow).where(
            CooldownWindow.fight_id == fight.id,
        )
    )

    fight_duration_ms = fight.end_time - fight.start_time

    if not damage_events:
        return 0

    # Get player classes
    result = await session.execute(
        select(
            FightPerformance.player_name,
            FightPerformance.player_class,
        ).where(FightPerformance.fight_id == fight.id)
    )
    player_classes = {r.player_name: r.player_class for r in result}

    # Group events by sourceID
    casts_by_source: dict[int, list[dict]] = {}
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is not None:
            casts_by_source.setdefault(sid, []).append(event)

    dmg_by_source: dict[int, list[dict]] = {}
    for event in damage_events:
        sid = event.get("sourceID")
        if sid is not None:
            dmg_by_source.setdefault(sid, []).append(event)

    total_rows = 0
    for source_id, player_casts in casts_by_source.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue
        player_class = player_classes.get(player_name)
        if not player_class:
            continue

        player_dmg = dmg_by_source.get(source_id, [])
        windows = compute_cooldown_windows(
            player_casts, player_dmg, player_class,
            fight_duration_ms, fight.start_time,
        )

        for w in windows:
            session.add(CooldownWindow(
                fight_id=fight.id,
                player_name=player_name,
                **w,
            ))
            total_rows += 1

    logger.info(
        "Ingested %d cooldown windows for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Boss phase detection =====

def detect_phases(
    encounter_name: str,
    fight_duration_ms: int,
) -> list[dict]:
    """Detect boss phases for an encounter.

    For encounters with defined phases, splits the fight duration evenly
    among phases (since we don't have HP% data from events API).
    For unknown encounters, returns a single "Full Fight" phase.
    """
    from shukketsu.pipeline.constants import ENCOUNTER_PHASES

    phase_defs = ENCOUNTER_PHASES.get(encounter_name, [])
    if not phase_defs:
        return [{
            "name": "Full Fight",
            "start_ms": 0,
            "end_ms": fight_duration_ms,
            "is_downtime": False,
        }]

    # Split fight duration evenly among phases
    phase_count = len(phase_defs)
    phase_duration = fight_duration_ms // phase_count
    phases = []
    for i, p in enumerate(phase_defs):
        start = i * phase_duration
        end = (
            (i + 1) * phase_duration
            if i < phase_count - 1
            else fight_duration_ms
        )
        phases.append({
            "name": p.name,
            "start_ms": start,
            "end_ms": end,
            "is_downtime": p.is_downtime,
        })

    return phases


def compute_phase_metrics(
    cast_events: list[dict],
    damage_events: list[dict],
    phases: list[dict],
    fight_start_time: int,
    fight_duration_ms: int,
) -> list[dict]:
    """Compute per-phase DPS and GCD uptime for a single player.

    Args:
        cast_events: Player's Casts events.
        damage_events: Player's DamageDone events.
        phases: List of phase dicts from detect_phases().
        fight_start_time: Absolute fight start time.
        fight_duration_ms: Total fight duration.

    Returns:
        List of dicts with phase_name, phase_dps, phase_casts,
        phase_gcd_uptime_pct.
    """
    results = []
    for phase in phases:
        p_start = phase["start_ms"]
        p_end = phase["end_ms"]
        p_duration = p_end - p_start

        # Count casts in this phase
        phase_casts = 0
        for event in cast_events:
            ts = event.get("timestamp", 0) - fight_start_time
            if p_start <= ts < p_end:
                phase_casts += 1

        # Sum damage in this phase
        phase_damage = 0
        for event in damage_events:
            ts = event.get("timestamp", 0) - fight_start_time
            if p_start <= ts < p_end:
                phase_damage += event.get("amount", 0)

        phase_dps = (
            round(phase_damage / (p_duration / 1000), 1)
            if p_duration > 0 else 0.0
        )

        # GCD uptime in phase
        active_ms = phase_casts * GCD_MS
        if active_ms > p_duration:
            active_ms = p_duration
        gcd_pct = (
            round(active_ms / p_duration * 100, 1)
            if p_duration > 0 else 0.0
        )

        results.append({
            "phase_name": phase["name"],
            "phase_start_ms": p_start,
            "phase_end_ms": p_end,
            "is_downtime": phase["is_downtime"],
            "phase_dps": phase_dps,
            "phase_casts": phase_casts,
            "phase_gcd_uptime_pct": gcd_pct,
        })

    return results


async def ingest_phases_for_fight(
    session, fight: Fight,
    cast_events: list[dict],
    damage_events: list[dict],
    actor_name_by_id: dict[int, str],
    encounter_name: str,
) -> int:
    """Compute and store per-phase metrics for all players in a fight."""
    await session.execute(
        delete(PhaseMetric).where(PhaseMetric.fight_id == fight.id)
    )

    fight_duration_ms = fight.end_time - fight.start_time
    phases = detect_phases(encounter_name, fight_duration_ms)

    # Only one "Full Fight" phase for unknown encounters -- skip
    if len(phases) == 1 and phases[0]["name"] == "Full Fight":
        return 0

    # Group events by sourceID
    casts_by_source: dict[int, list[dict]] = {}
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is not None:
            casts_by_source.setdefault(sid, []).append(event)

    dmg_by_source: dict[int, list[dict]] = {}
    for event in (damage_events or []):
        sid = event.get("sourceID")
        if sid is not None:
            dmg_by_source.setdefault(sid, []).append(event)

    total_rows = 0
    for source_id, player_casts in casts_by_source.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue

        player_dmg = dmg_by_source.get(source_id, [])
        metrics = compute_phase_metrics(
            player_casts, player_dmg, phases,
            fight.start_time, fight_duration_ms,
        )

        for m in metrics:
            session.add(PhaseMetric(
                fight_id=fight.id,
                player_name=player_name,
                **m,
            ))
            total_rows += 1

    logger.info(
        "Ingested %d phase metrics for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== DoT refresh detection =====

def compute_dot_refreshes(
    cast_events: list[dict],
    player_class: str,
) -> list[dict]:
    """Detect early DoT refreshes from cast events for a single player.

    A refresh is "early" if the DoT was reapplied before the pandemic window
    (last 30% of the DoT duration). Early refreshes clip remaining ticks.

    Args:
        cast_events: Sorted Casts events for one player.
        player_class: WoW class name.

    Returns:
        List of dicts per DoT spell with refresh stats.
    """
    from shukketsu.pipeline.constants import CLASS_DOTS

    dot_defs = CLASS_DOTS.get(player_class, [])
    if not dot_defs:
        return []

    dot_by_spell = {d.spell_id: d for d in dot_defs}

    # Track last application timestamp per spell
    last_apply: dict[int, int] = {}
    refresh_data: dict[int, dict] = {}

    for event in cast_events:
        spell_id = event.get("abilityGameID", 0)
        if spell_id not in dot_by_spell:
            continue

        dot = dot_by_spell[spell_id]
        ts = event.get("timestamp", 0)

        if spell_id not in refresh_data:
            refresh_data[spell_id] = {
                "spell_id": spell_id,
                "ability_name": dot.name,
                "total_refreshes": 0,
                "early_refreshes": 0,
                "remaining_sum_ms": 0,
                "clipped_ticks": 0,
            }

        if spell_id in last_apply:
            # This is a refresh
            elapsed = ts - last_apply[spell_id]
            remaining = dot.duration_ms - elapsed
            refresh_data[spell_id]["total_refreshes"] += 1

            if remaining > 0:
                # Safe refresh window starts at duration - pandemic_window
                safe_start = dot.duration_ms - dot.pandemic_window_ms
                if elapsed < safe_start:
                    # Early refresh -- DoT refreshed before pandemic window
                    refresh_data[spell_id]["early_refreshes"] += 1
                    refresh_data[spell_id]["remaining_sum_ms"] += remaining
                    clipped = int(remaining // dot.tick_interval_ms)
                    refresh_data[spell_id]["clipped_ticks"] += clipped

        last_apply[spell_id] = ts

    results = []
    for _spell_id, data in refresh_data.items():
        total = data["total_refreshes"]
        early = data["early_refreshes"]
        early_pct = round(early / total * 100, 1) if total > 0 else 0.0
        avg_remaining = (
            round(data["remaining_sum_ms"] / early, 1) if early > 0 else 0.0
        )

        results.append({
            "spell_id": data["spell_id"],
            "ability_name": data["ability_name"],
            "total_refreshes": total,
            "early_refreshes": early,
            "early_refresh_pct": early_pct,
            "avg_remaining_ms": avg_remaining,
            "clipped_ticks_est": data["clipped_ticks"],
        })

    return results


async def ingest_dot_refreshes_for_fight(
    session, fight: Fight, cast_events: list[dict],
    actor_name_by_id: dict[int, str],
) -> int:
    """Compute and store DoT refresh metrics for all players in a fight."""
    await session.execute(
        delete(DotRefresh).where(DotRefresh.fight_id == fight.id)
    )

    if not cast_events:
        return 0

    # Get player classes
    result = await session.execute(
        select(FightPerformance.player_name, FightPerformance.player_class)
        .where(FightPerformance.fight_id == fight.id)
    )
    player_classes = {r.player_name: r.player_class for r in result}

    # Group by sourceID
    events_by_source: dict[int, list[dict]] = {}
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is not None:
            events_by_source.setdefault(sid, []).append(event)

    total_rows = 0
    for source_id, player_events in events_by_source.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue

        player_class = player_classes.get(player_name)
        if not player_class:
            continue

        refreshes = compute_dot_refreshes(player_events, player_class)
        for r in refreshes:
            session.add(DotRefresh(
                fight_id=fight.id,
                player_name=player_name,
                **r,
            ))
            total_rows += 1

    logger.info(
        "Ingested %d DoT refresh rows for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Rotation score evaluation =====

async def ingest_rotation_scores_for_fight(
    session, fight: Fight, cast_events: list[dict],
    actor_name_by_id: dict[int, str],
) -> int:
    """Evaluate and store rotation scores for players with defined rules."""
    from shukketsu.db.models import BuffUptime
    from shukketsu.pipeline.rotation_rules import (
        SPEC_ROTATIONS,
        evaluate_rotation,
    )

    await session.execute(
        delete(RotationScore).where(RotationScore.fight_id == fight.id)
    )

    if not cast_events:
        return 0

    # Get player specs
    result = await session.execute(
        select(
            FightPerformance.player_name,
            FightPerformance.player_spec,
        ).where(FightPerformance.fight_id == fight.id)
    )
    player_specs = {r.player_name: r.player_spec for r in result}

    # Get buff uptimes for all players in this fight
    buff_result = await session.execute(
        select(
            BuffUptime.player_name,
            BuffUptime.spell_id,
            BuffUptime.uptime_pct,
        ).where(BuffUptime.fight_id == fight.id)
    )
    player_buffs: dict[str, dict[int, float]] = {}
    for r in buff_result:
        player_buffs.setdefault(
            r.player_name, {},
        )[r.spell_id] = r.uptime_pct

    # Group cast events by sourceID
    events_by_source: dict[int, list[dict]] = {}
    for event in cast_events:
        sid = event.get("sourceID")
        if sid is not None:
            events_by_source.setdefault(sid, []).append(event)

    fight_duration_ms = fight.end_time - fight.start_time
    total_rows = 0

    for source_id, player_events in events_by_source.items():
        player_name = actor_name_by_id.get(source_id)
        if not player_name:
            continue

        spec = player_specs.get(player_name)
        if not spec or spec not in SPEC_ROTATIONS:
            continue

        buffs = player_buffs.get(player_name, {})
        report = evaluate_rotation(
            player_events, buffs, spec, fight_duration_ms,
        )

        violations_json = (
            json.dumps(report.violations)
            if report.violations else None
        )

        session.add(RotationScore(
            fight_id=fight.id,
            player_name=player_name,
            spec=report.spec,
            score_pct=report.score_pct,
            rules_checked=report.rules_checked,
            rules_passed=report.rules_passed,
            violations_json=violations_json,
        ))
        total_rows += 1

    logger.info(
        "Ingested %d rotation scores for fight %d (%s)",
        total_rows, fight.fight_id, fight.report_code,
    )
    return total_rows


# ===== Report-level orchestration =====

async def ingest_event_data_for_report(
    wcl, session, report_code: str,
) -> int:
    """Ingest event data (deaths, cast metrics, cooldowns) for all fights in a report.

    Returns total rows inserted across all event types.
    """
    from shukketsu.wcl.events import fetch_all_events

    fights = await session.execute(
        select(Fight).where(Fight.report_code == report_code)
    )
    fight_list = list(fights.scalars().all())

    if not fight_list:
        logger.warning("No fights found for report %s", report_code)
        return 0

    # Build actor name-by-id from the report's masterData
    # We need to fetch the report fights data to get masterData
    from shukketsu.wcl.queries import REPORT_FIGHTS

    rate_limit_frag = "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"
    report_data = await wcl.query(
        REPORT_FIGHTS.replace("RATE_LIMIT", rate_limit_frag),
        variables={"code": report_code},
    )
    report_info = report_data["reportData"]["report"]
    master_data = report_info.get("masterData", {})
    actor_name_by_id: dict[int, str] = {}
    for actor in master_data.get("actors", []):
        actor_name_by_id[actor["id"]] = actor["name"]

    total_rows = 0
    for fight in fight_list:
        fight_duration_ms = fight.end_time - fight.start_time

        # 1. Deaths
        death_rows = await ingest_deaths_for_fight(
            wcl, session, report_code, fight, actor_name_by_id,
        )
        total_rows += death_rows

        # 2. Fetch Casts events ONCE per fight (reuse for both metrics)
        try:
            cast_events = await fetch_all_events(
                wcl, report_code, fight.start_time, fight.end_time, "Casts",
            )
        except Exception:
            logger.exception(
                "Failed to fetch Casts events for fight %d in %s",
                fight.fight_id, report_code,
            )
            cast_events = []

        # 3. Cast metrics
        cast_rows = await ingest_casts_for_fight(
            session, fight, cast_events, actor_name_by_id, fight_duration_ms,
        )
        total_rows += cast_rows

        # 4. Cooldown usage
        cd_rows = await ingest_cooldowns_for_fight(
            session, fight, cast_events, actor_name_by_id, fight_duration_ms,
        )
        total_rows += cd_rows

        # 5. Cancelled casts
        cancel_rows = await ingest_cancelled_casts_for_fight(
            session, fight, cast_events, actor_name_by_id,
        )
        total_rows += cancel_rows

        # 6. Cast events (for timeline)
        timeline_rows = await ingest_cast_events_for_fight(
            session, fight, cast_events, actor_name_by_id,
        )
        total_rows += timeline_rows

        # 7. Resource snapshots (separate API call)
        resource_rows = await ingest_resources_for_fight(
            wcl, session, report_code, fight, actor_name_by_id,
        )
        total_rows += resource_rows

        # 8. Fetch DamageDone events ONCE (reused by CD windows + phases)
        try:
            damage_events = await fetch_all_events(
                wcl, report_code,
                fight.start_time, fight.end_time, "DamageDone",
            )
        except Exception:
            logger.exception(
                "Failed to fetch DamageDone for fight %d in %s",
                fight.fight_id, report_code,
            )
            damage_events = []

        # 9. Cooldown window throughput
        window_rows = await ingest_cooldown_windows_for_fight(
            session, fight,
            cast_events, damage_events, actor_name_by_id,
        )
        total_rows += window_rows

        # 10. Phase metrics
        encounter_result = await session.execute(
            select(Fight.encounter_id).where(Fight.id == fight.id)
        )
        enc_row = encounter_result.fetchone()
        encounter_name = ""
        if enc_row:
            from shukketsu.db.models import Encounter

            enc = await session.get(Encounter, enc_row.encounter_id)
            encounter_name = enc.name if enc else ""

        phase_rows = await ingest_phases_for_fight(
            session, fight,
            cast_events, damage_events, actor_name_by_id, encounter_name,
        )
        total_rows += phase_rows

        # 11. DoT refresh detection (reuses cast_events)
        dot_rows = await ingest_dot_refreshes_for_fight(
            session, fight, cast_events, actor_name_by_id,
        )
        total_rows += dot_rows

        # 12. Rotation score evaluation (reuses cast_events)
        rotation_rows = await ingest_rotation_scores_for_fight(
            session, fight, cast_events, actor_name_by_id,
        )
        total_rows += rotation_rows

    logger.info(
        "Ingested event data for report %s: %d total rows across %d fights",
        report_code, total_rows, len(fight_list),
    )
    return total_rows
