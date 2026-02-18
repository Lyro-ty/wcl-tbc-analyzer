"""Pipeline for ingesting WCL cast events and computing derived metrics."""

import json
import logging
import math
from collections import defaultdict

from sqlalchemy import delete

from shukketsu.db.models import (
    CancelledCast,
    CastEvent,
    CastMetric,
    CooldownUsage,
)
from shukketsu.pipeline.constants import CLASSIC_COOLDOWNS
from shukketsu.wcl.events import fetch_all_events

logger = logging.getLogger(__name__)

# Global Combat Design constants
GCD_MS = 1500          # Global cooldown in milliseconds
GAP_THRESHOLD_MS = 2500  # Gaps longer than this are tracked


def parse_cast_events(
    events: list[dict],
    fight_id: int,
    actors: dict[int, str],
) -> list[CastEvent]:
    """Parse raw WCL cast events into CastEvent ORM objects.

    Args:
        events: Raw WCL events (dataType="Casts").
        fight_id: Internal DB fight ID (fights.id).
        actors: Mapping of WCL sourceID -> player_name. Events with
                sourceID not in this mapping (NPCs) are skipped.

    Returns:
        List of CastEvent ORM objects ready for insertion.
    """
    results: list[CastEvent] = []
    for event in events:
        event_type = event.get("type")
        if event_type not in ("cast", "begincast"):
            continue

        source_id = event.get("sourceID")
        player_name = actors.get(source_id)
        if player_name is None:
            continue

        ability = event.get("ability") or {}
        target = event.get("target") or {}

        results.append(CastEvent(
            fight_id=fight_id,
            player_name=player_name,
            timestamp_ms=event.get("timestamp", 0),
            spell_id=ability.get("guid", 0),
            ability_name=ability.get("name", f"Spell-{ability.get('guid', 0)}"),
            event_type=event_type,
            target_name=target.get("name") or None,
        ))

    return results


def compute_cast_metrics(
    cast_events: list[CastEvent],
    fight_duration_ms: int,
) -> dict[str, CastMetric]:
    """Compute GCD uptime, CPM, and gap analysis per player.

    Args:
        cast_events: Parsed CastEvent objects for a single fight.
        fight_duration_ms: Total fight duration in milliseconds.

    Returns:
        Dict keyed by player_name -> CastMetric ORM object (without fight_id set).
    """
    if fight_duration_ms <= 0:
        return {}

    # Group completed casts by player
    casts_by_player: dict[str, list[int]] = defaultdict(list)
    for ce in cast_events:
        if ce.event_type == "cast":
            casts_by_player[ce.player_name].append(ce.timestamp_ms)

    results: dict[str, CastMetric] = {}
    for player_name, timestamps in casts_by_player.items():
        timestamps.sort()
        total_casts = len(timestamps)
        cpm = total_casts / (fight_duration_ms / 60_000)

        # GCD uptime: for each cast, credit min(GCD, gap_to_next).
        # Last cast gets full GCD credit (capped at remaining fight time).
        active_time = 0
        gaps: list[tuple[int, int]] = []  # (gap_ms, gap_start_timestamp)

        for i in range(total_casts):
            if i < total_casts - 1:
                gap_to_next = timestamps[i + 1] - timestamps[i]
                active_time += min(GCD_MS, gap_to_next)
                if gap_to_next > GAP_THRESHOLD_MS:
                    gaps.append((gap_to_next, timestamps[i]))
            else:
                # Last cast: credit GCD (capped by fight duration remaining)
                active_time += GCD_MS

        # Cap active_time at fight_duration_ms
        active_time = min(active_time, fight_duration_ms)
        gcd_uptime_pct = active_time / fight_duration_ms * 100
        downtime = fight_duration_ms - active_time

        # Gap statistics
        gap_count = len(gaps)
        longest_gap_ms = 0
        longest_gap_at_ms = 0
        avg_gap_ms = 0.0
        if gaps:
            longest = max(gaps, key=lambda g: g[0])
            longest_gap_ms = longest[0]
            longest_gap_at_ms = longest[1]
            avg_gap_ms = sum(g[0] for g in gaps) / gap_count

        results[player_name] = CastMetric(
            player_name=player_name,
            total_casts=total_casts,
            casts_per_minute=round(cpm, 2),
            gcd_uptime_pct=round(gcd_uptime_pct, 1),
            active_time_ms=active_time,
            downtime_ms=downtime,
            longest_gap_ms=longest_gap_ms,
            longest_gap_at_ms=longest_gap_at_ms,
            avg_gap_ms=round(avg_gap_ms, 1),
            gap_count=gap_count,
        )

    return results


def compute_cooldown_usage(
    cast_events: list[CastEvent],
    fight_duration_ms: int,
    player_class_map: dict[str, str],
) -> list[CooldownUsage]:
    """Compute cooldown efficiency per player per cooldown ability.

    Args:
        cast_events: Parsed CastEvent objects for a single fight.
        fight_duration_ms: Total fight duration in milliseconds.
        player_class_map: Mapping of player_name -> class_name.

    Returns:
        List of CooldownUsage ORM objects (without fight_id set).
    """
    if fight_duration_ms <= 0:
        return []

    # Index completed casts by (player, spell_id)
    casts_by_player_spell: dict[tuple[str, int], list[int]] = defaultdict(list)
    for ce in cast_events:
        if ce.event_type == "cast":
            casts_by_player_spell[(ce.player_name, ce.spell_id)].append(
                ce.timestamp_ms
            )

    results: list[CooldownUsage] = []
    for player_name, class_name in player_class_map.items():
        cooldowns = CLASSIC_COOLDOWNS.get(class_name, [])
        for cd in cooldowns:
            if cd.cooldown_sec <= 0:
                continue

            key = (player_name, cd.spell_id)
            timestamps = casts_by_player_spell.get(key, [])
            times_used = len(timestamps)
            max_possible = math.floor(
                fight_duration_ms / (cd.cooldown_sec * 1000)
            ) + 1
            efficiency = (times_used / max_possible * 100) if max_possible > 0 else 0.0

            first_use = min(timestamps) if timestamps else None
            last_use = max(timestamps) if timestamps else None

            results.append(CooldownUsage(
                player_name=player_name,
                spell_id=cd.spell_id,
                ability_name=cd.name,
                cooldown_sec=cd.cooldown_sec,
                times_used=times_used,
                max_possible_uses=max_possible,
                first_use_ms=first_use,
                last_use_ms=last_use,
                efficiency_pct=round(efficiency, 1),
            ))

    return results


def compute_cancelled_casts(
    cast_events: list[CastEvent],
) -> dict[str, CancelledCast]:
    """Compute cancel rates per player by comparing begincast vs cast counts.

    Args:
        cast_events: Parsed CastEvent objects for a single fight.

    Returns:
        Dict keyed by player_name -> CancelledCast ORM object (without fight_id set).
    """
    # Per-player totals
    begins_by_player: dict[str, int] = defaultdict(int)
    completions_by_player: dict[str, int] = defaultdict(int)

    # Per-player per-spell counts for top cancelled
    spell_begins: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    spell_completions: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    spell_names: dict[int, str] = {}

    for ce in cast_events:
        if ce.event_type == "begincast":
            begins_by_player[ce.player_name] += 1
            spell_begins[ce.player_name][ce.spell_id] += 1
        elif ce.event_type == "cast":
            completions_by_player[ce.player_name] += 1
            spell_completions[ce.player_name][ce.spell_id] += 1
        spell_names[ce.spell_id] = ce.ability_name

    # All players who had any begincast or cast events
    all_players = set(begins_by_player.keys()) | set(completions_by_player.keys())

    results: dict[str, CancelledCast] = {}
    for player_name in all_players:
        total_begins = begins_by_player.get(player_name, 0)
        total_completions = completions_by_player.get(player_name, 0)
        cancel_count = max(0, total_begins - total_completions)
        cancel_pct = (
            (cancel_count / total_begins * 100) if total_begins > 0 else 0.0
        )

        # Top cancelled spells: per-spell begincast - cast, top 5
        player_spell_begins = spell_begins.get(player_name, {})
        player_spell_completions = spell_completions.get(player_name, {})
        all_spell_ids = set(player_spell_begins.keys())

        spell_cancels: list[dict] = []
        for spell_id in all_spell_ids:
            sb = player_spell_begins.get(spell_id, 0)
            sc = player_spell_completions.get(spell_id, 0)
            diff = sb - sc
            if diff > 0:
                spell_cancels.append({
                    "spell_id": spell_id,
                    "name": spell_names.get(spell_id, f"Spell-{spell_id}"),
                    "cancel_count": diff,
                })

        spell_cancels.sort(key=lambda x: x["cancel_count"], reverse=True)
        top_cancelled = spell_cancels[:5]

        results[player_name] = CancelledCast(
            player_name=player_name,
            total_begins=total_begins,
            total_completions=total_completions,
            cancel_count=cancel_count,
            cancel_pct=round(cancel_pct, 1),
            top_cancelled_json=json.dumps(top_cancelled) if top_cancelled else None,
        )

    return results


async def ingest_cast_events_for_fight(
    wcl,
    session,
    report_code: str,
    fight,
    actors: dict[int, str],
    player_class_map: dict[str, str],
) -> int:
    """Fetch and ingest cast events + derived metrics for a single fight.

    Args:
        wcl: WCLClient instance.
        session: Async SQLAlchemy session.
        report_code: WCL report code.
        fight: Fight ORM object with .id, .start_time, .end_time, .fight_id.
        actors: Mapping of WCL sourceID -> player_name.
        player_class_map: Mapping of player_name -> class_name.

    Returns:
        Total count of rows inserted across all tables.
    """
    try:
        # Delete existing data for this fight (idempotent re-ingest)
        for model in (CastEvent, CastMetric, CooldownUsage, CancelledCast):
            await session.execute(
                delete(model).where(model.fight_id == fight.id)
            )

        # Fetch cast events from WCL (async generator yields pages)
        all_events: list[dict] = []
        async for page in fetch_all_events(
            wcl, report_code, fight.start_time, fight.end_time,
            data_type="Casts",
        ):
            all_events.extend(page)

        if not all_events:
            return 0

        # Parse raw events into CastEvent ORM objects
        cast_event_rows = parse_cast_events(all_events, fight.id, actors)
        for row in cast_event_rows:
            session.add(row)

        total_rows = len(cast_event_rows)
        fight_duration_ms = fight.end_time - fight.start_time

        # Compute and insert derived metrics
        metrics = compute_cast_metrics(cast_event_rows, fight_duration_ms)
        for metric in metrics.values():
            metric.fight_id = fight.id
            session.add(metric)
        total_rows += len(metrics)

        cd_usage = compute_cooldown_usage(
            cast_event_rows, fight_duration_ms, player_class_map,
        )
        for cu in cd_usage:
            cu.fight_id = fight.id
            session.add(cu)
        total_rows += len(cd_usage)

        cancelled = compute_cancelled_casts(cast_event_rows)
        for cc in cancelled.values():
            cc.fight_id = fight.id
            session.add(cc)
        total_rows += len(cancelled)

        await session.flush()

        logger.info(
            "Ingested cast data for fight %d (%s): %d events, %d metrics, "
            "%d cooldowns, %d cancelled",
            fight.fight_id, report_code,
            len(cast_event_rows), len(metrics),
            len(cd_usage), len(cancelled),
        )
        return total_rows

    except Exception:
        logger.exception(
            "Failed to ingest cast events for fight %d in %s",
            fight.fight_id, report_code,
        )
        return 0
