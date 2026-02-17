"""Pipeline for ingesting WCL events data (deaths, cast metrics, cooldowns)."""

import json
import logging

from sqlalchemy import delete, select

from shukketsu.db.models import (
    CastMetric,
    CooldownUsage,
    DeathDetail,
    Fight,
    FightPerformance,
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

    logger.info(
        "Ingested event data for report %s: %d total rows across %d fights",
        report_code, total_rows, len(fight_list),
    )
    return total_rows
