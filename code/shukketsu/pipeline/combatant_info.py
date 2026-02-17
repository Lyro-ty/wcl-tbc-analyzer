"""Parse WCL CombatantInfo events into consumables and gear snapshots."""

import logging

from sqlalchemy import delete, select

from shukketsu.db.models import Fight, FightConsumable, GearSnapshot
from shukketsu.pipeline.constants import CONSUMABLE_CATEGORIES

logger = logging.getLogger(__name__)


def parse_consumables(
    auras: list[dict], fight_id: int, player_name: str
) -> list[FightConsumable]:
    """Extract consumable buffs from CombatantInfo auras.

    Only auras whose spell ID appears in CONSUMABLE_CATEGORIES are included.
    Unknown auras are silently skipped.
    """
    result = []
    for aura in auras:
        spell_id = aura.get("ability", 0)
        if spell_id in CONSUMABLE_CATEGORIES:
            category, display_name = CONSUMABLE_CATEGORIES[spell_id]
            result.append(FightConsumable(
                fight_id=fight_id,
                player_name=player_name,
                category=category,
                spell_id=spell_id,
                ability_name=display_name,
                active=True,
            ))
    return result


def parse_gear(
    gear_list: list[dict], fight_id: int, player_name: str
) -> list[GearSnapshot]:
    """Extract gear from CombatantInfo gear array.

    Items with id=0 (empty slots) are skipped.
    """
    result = []
    for item in gear_list:
        item_id = item.get("id", 0)
        if item_id == 0:
            continue
        result.append(GearSnapshot(
            fight_id=fight_id,
            player_name=player_name,
            slot=item.get("slot", 0),
            item_id=item_id,
            item_level=item.get("itemLevel", 0),
        ))
    return result


async def ingest_combatant_info_for_report(
    wcl, session, report_code: str,
) -> int:
    """Fetch CombatantInfo events for all fights in a report and store consumables + gear.

    Uses the same paginated fetch_all_events function as other event types.
    CombatantInfo events contain auras (buffs including consumables) and gear
    arrays per player at the start of each fight.

    Returns total rows inserted (consumables + gear items).
    """
    from shukketsu.wcl.events import fetch_all_events

    # Get all fights for this report
    result = await session.execute(
        select(Fight).where(Fight.report_code == report_code)
    )
    fights = result.scalars().all()
    if not fights:
        return 0

    total_rows = 0

    for fight in fights:
        # Delete existing data for idempotency
        await session.execute(
            delete(FightConsumable).where(FightConsumable.fight_id == fight.id)
        )
        await session.execute(
            delete(GearSnapshot).where(GearSnapshot.fight_id == fight.id)
        )

        # Fetch CombatantInfo events
        try:
            events = await fetch_all_events(
                wcl, report_code, fight.start_time, fight.end_time,
                data_type="CombatantInfo",
            )
        except Exception:
            logger.exception(
                "Failed to fetch CombatantInfo events for fight %d in %s",
                fight.fight_id, report_code,
            )
            continue

        for event in events:
            # CombatantInfo events include a "name" field for the player
            player_name = event.get(
                "name", f"Unknown-{event.get('sourceID', 0)}"
            )

            # Parse auras for consumables
            auras = event.get("auras", [])
            consumables = parse_consumables(auras, fight.id, player_name)
            for c in consumables:
                session.add(c)
                total_rows += 1

            # Parse gear
            gear = event.get("gear", [])
            gear_items = parse_gear(gear, fight.id, player_name)
            for g in gear_items:
                session.add(g)
                total_rows += 1

    await session.flush()

    logger.info(
        "Ingested combatant info for report %s: %d total rows across %d fights",
        report_code, total_rows, len(list(fights)),
    )
    return total_rows
