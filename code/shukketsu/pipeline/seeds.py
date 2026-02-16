"""Seed encounter data from WCL API or static lists."""

import logging

from shukketsu.db.models import Encounter

logger = logging.getLogger(__name__)


async def seed_encounters_from_list(session, encounters: list[dict]) -> int:
    """Upsert encounters into DB.

    Each dict has keys: id, name, zone_id, zone_name, difficulty.
    Uses session.merge() for idempotent upsert (same as ingest.py pattern).
    Returns count of encounters seeded.
    """
    count = 0
    for enc in encounters:
        await session.merge(Encounter(
            id=enc["id"],
            name=enc["name"],
            zone_id=enc.get("zone_id", 0),
            zone_name=enc.get("zone_name", "Unknown"),
            difficulty=enc.get("difficulty", 0),
        ))
        count += 1
    await session.flush()
    logger.info("Seeded %d encounters", count)
    return count


async def discover_and_seed_encounters(wcl, session, zone_ids: list[int]) -> list[dict]:
    """Query WCL API for each zone, discover encounters, seed into DB.

    Returns list of discovered encounter dicts.
    """
    from shukketsu.wcl.queries import ZONE_ENCOUNTERS

    all_encounters = []
    for zone_id in zone_ids:
        data = await wcl.query(
            ZONE_ENCOUNTERS.replace(
                "RATE_LIMIT",
                "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }",
            ),
            variables={"zoneID": zone_id},
        )
        zone = data["worldData"]["zone"]
        if zone is None:
            logger.warning("Zone %d not found in WCL API", zone_id)
            continue
        zone_name = zone["name"]
        for enc in zone["encounters"]:
            encounter = {
                "id": enc["id"],
                "name": enc["name"],
                "zone_id": zone_id,
                "zone_name": zone_name,
                "difficulty": 0,
            }
            all_encounters.append(encounter)

    if all_encounters:
        await seed_encounters_from_list(session, all_encounters)

    return all_encounters
