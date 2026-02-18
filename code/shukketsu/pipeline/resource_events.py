"""Pipeline for ingesting WCL resource events into resource_snapshots table."""

import json
import logging
from collections import defaultdict

from sqlalchemy import delete

from shukketsu.db.models import ResourceSnapshot
from shukketsu.wcl.events import fetch_all_events

logger = logging.getLogger(__name__)

RESOURCE_TYPE_NAMES = {0: "Mana", 1: "Rage", 3: "Energy"}

# Target number of samples for charting
_TARGET_SAMPLES = 50


def compute_resource_snapshots(
    events: list[dict],
    fight_id: int,
    fight_duration_ms: int,
    actors: dict[int, str],
    fight_start_time: int = 0,
) -> list[ResourceSnapshot]:
    """Parse WCL ResourceChange events into per-player per-resource-type snapshots.

    Args:
        events: Raw WCL events (dataType="Resources").
        fight_id: Internal DB fight ID (fights.id).
        fight_duration_ms: Total fight duration in milliseconds.
        actors: Mapping of WCL sourceID -> player_name.

    Returns:
        List of ResourceSnapshot ORM objects ready for insertion.
    """
    if not events or fight_duration_ms <= 0:
        return []

    # Group events by (player_name, resource_type_id)
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)

    for event in events:
        source_id = event.get("sourceID")
        player_name = actors.get(source_id)
        if player_name is None:
            continue

        class_resources = event.get("classResources")
        if not class_resources:
            continue

        resource_type_id = class_resources[0].get("type")
        if resource_type_id is None:
            continue

        grouped[(player_name, resource_type_id)].append(event)

    results: list[ResourceSnapshot] = []

    for (player_name, resource_type_id), player_events in grouped.items():
        resource_name = RESOURCE_TYPE_NAMES.get(resource_type_id)
        if resource_name is None:
            continue

        # Sort events by timestamp
        player_events.sort(key=lambda e: e.get("timestamp", 0))

        # Extract resource amounts from classResources[0].amount
        amounts: list[int] = []
        timestamps: list[int] = []
        for ev in player_events:
            cr = ev["classResources"][0]
            amount = cr.get("amount", 0)
            amounts.append(amount)
            timestamps.append(ev.get("timestamp", 0))

        if not amounts:
            continue

        min_val = min(amounts)
        max_val = max(amounts)
        avg_val = sum(amounts) / len(amounts)

        # Compute time_at_zero: walk events in order, accumulate time where
        # resource == 0. For each event where amount == 0, the "zero time"
        # extends from this event's timestamp until the next event's timestamp
        # (or end of fight for the last event).
        time_at_zero_ms = 0
        for i, amount in enumerate(amounts):
            if amount == 0:
                if i < len(amounts) - 1:
                    delta = timestamps[i + 1] - timestamps[i]
                else:
                    # Last event: count from this timestamp to end of fight.
                    fight_end = (
                        fight_start_time + fight_duration_ms
                        if fight_start_time
                        else timestamps[0] + fight_duration_ms
                    )
                    delta = fight_end - timestamps[i]
                time_at_zero_ms += max(0, delta)

        time_at_zero_pct = min(round(time_at_zero_ms / fight_duration_ms * 100, 1), 100.0)

        # Build samples_json: downsample to ~_TARGET_SAMPLES data points
        if len(amounts) <= _TARGET_SAMPLES:
            samples = [
                {"t": timestamps[i], "v": amounts[i]}
                for i in range(len(amounts))
            ]
        else:
            step = len(amounts) / _TARGET_SAMPLES
            samples = []
            for s in range(_TARGET_SAMPLES):
                idx = int(s * step)
                samples.append({"t": timestamps[idx], "v": amounts[idx]})

        results.append(ResourceSnapshot(
            fight_id=fight_id,
            player_name=player_name,
            resource_type=resource_name,
            min_value=min_val,
            max_value=max_val,
            avg_value=round(avg_val, 1),
            time_at_zero_ms=time_at_zero_ms,
            time_at_zero_pct=time_at_zero_pct,
            samples_json=json.dumps(samples),
        ))

    return results


async def ingest_resource_data_for_fight(
    wcl,
    session,
    report_code: str,
    fight,
    actors: dict[int, str],
) -> int:
    """Fetch and ingest resource events for a single fight.

    Args:
        wcl: WCLClient instance.
        session: Async SQLAlchemy session.
        report_code: WCL report code.
        fight: Fight ORM object with .id, .start_time, .end_time, .fight_id.
        actors: Mapping of WCL sourceID -> player_name.

    Returns:
        Count of resource_snapshots rows inserted.
    """
    # Delete existing resource_snapshots for this fight (idempotent)
    await session.execute(
        delete(ResourceSnapshot).where(ResourceSnapshot.fight_id == fight.id)
    )

    # Fetch resource events from WCL (async generator yields pages)
    all_events: list[dict] = []
    async for page in fetch_all_events(
        wcl, report_code, fight.start_time, fight.end_time,
        data_type="Resources",
    ):
        all_events.extend(page)

    if not all_events:
        return 0

    fight_duration_ms = fight.end_time - fight.start_time

    # Compute snapshots and insert
    snapshots = compute_resource_snapshots(
        all_events, fight.id, fight_duration_ms, actors,
        fight_start_time=fight.start_time,
    )
    for snapshot in snapshots:
        session.add(snapshot)
    await session.flush()

    logger.info(
        "Ingested %d resource snapshots for fight %d (%s)",
        len(snapshots), fight.fight_id, report_code,
    )
    return len(snapshots)
