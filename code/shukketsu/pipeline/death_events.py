"""Pipeline for ingesting WCL death events into death_details table."""

import json
import logging
from collections import defaultdict

from sqlalchemy import delete

from shukketsu.db.models import DeathDetail
from shukketsu.wcl.events import fetch_all_events

logger = logging.getLogger(__name__)


def parse_death_events(events: list[dict], fight_id: int) -> list[DeathDetail]:
    """Parse raw WCL death events into DeathDetail ORM objects.

    Args:
        events: List of raw death event dicts from WCL events API (dataType="Deaths").
        fight_id: Internal DB fight ID (fights.id, not the WCL fight_id).

    Returns:
        List of DeathDetail ORM objects ready for insertion.
    """
    if not events:
        return []

    death_index_by_player: dict[str, int] = defaultdict(int)
    results: list[DeathDetail] = []

    for event in events:
        # Extract player name from target
        target = event.get("target") or {}
        player_name = target.get("name", "Unknown")

        # Extract killing blow ability
        ability = event.get("ability") or {}
        killing_blow_ability = ability.get("name", "Unknown")

        # Extract killing blow source
        source = event.get("source") or {}
        killing_blow_source = source.get("name", "Unknown")

        # Timestamp (ms relative to fight start)
        timestamp_ms = event.get("timestamp", 0)

        # Nested damage events leading to death
        nested_events = event.get("events") or []

        # Calculate total damage taken from nested events
        damage_taken_total = sum(
            e.get("amount", 0) for e in nested_events
        )

        # Build events_json from last 5 damage events
        last_events = nested_events[-5:] if len(nested_events) > 5 else nested_events
        events_summary = []
        for e in last_events:
            e_source = e.get("source") or {}
            e_ability = e.get("ability") or {}
            events_summary.append({
                "ts": e.get("timestamp", 0),
                "ability": e_ability.get("name", "Unknown"),
                "amount": e.get("amount", 0),
                "source": e_source.get("name", "Unknown"),
            })
        events_json = json.dumps(events_summary)

        # Death index per player (0-based, sequential)
        idx = death_index_by_player[player_name]
        death_index_by_player[player_name] += 1

        results.append(DeathDetail(
            fight_id=fight_id,
            player_name=player_name,
            death_index=idx,
            timestamp_ms=timestamp_ms,
            killing_blow_ability=killing_blow_ability,
            killing_blow_source=killing_blow_source,
            damage_taken_total=damage_taken_total,
            events_json=events_json,
        ))

    return results


async def ingest_death_events_for_fight(
    wcl, session, report_code: str, fight,
) -> int:
    """Fetch and ingest death events for a single fight.

    Args:
        wcl: WCLClient instance.
        session: Async SQLAlchemy session.
        report_code: WCL report code.
        fight: Fight ORM object with .id, .start_time, .end_time, .fight_id.

    Returns:
        Count of death_details rows inserted.
    """
    try:
        # Delete existing death_details for this fight (idempotent)
        await session.execute(
            delete(DeathDetail).where(DeathDetail.fight_id == fight.id)
        )

        # Fetch death events from WCL
        events = await fetch_all_events(
            wcl, report_code, fight.start_time, fight.end_time,
            data_type="Deaths",
        )

        if not events:
            return 0

        # Parse and insert
        details = parse_death_events(events, fight.id)
        for detail in details:
            session.add(detail)
        await session.flush()

        logger.info(
            "Ingested %d death details for fight %d (%s)",
            len(details), fight.fight_id, report_code,
        )
        return len(details)

    except Exception:
        logger.exception(
            "Failed to ingest death events for fight %d in %s",
            fight.fight_id, report_code,
        )
        return 0
