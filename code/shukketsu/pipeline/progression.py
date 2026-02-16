import logging
from datetime import UTC, datetime
from statistics import median

from sqlalchemy import select

from shukketsu.db.models import (
    Fight,
    FightPerformance,
    MyCharacter,
    ProgressionSnapshot,
)

logger = logging.getLogger(__name__)


async def compute_progression_snapshot(
    session,
    character: MyCharacter,
    encounter_id: int,
    snapshot_time: datetime,
) -> ProgressionSnapshot | None:
    """Compute a progression snapshot for one character on one encounter.

    Aggregates kill data from fight_performances for this character+encounter.
    Returns None if no kill data exists.
    """
    # Find all fight performances for this character on this encounter (kills only)
    result = await session.execute(
        select(FightPerformance)
        .join(Fight, FightPerformance.fight_id == Fight.id)
        .where(
            Fight.encounter_id == encounter_id,
            Fight.kill == True,  # noqa: E712
            FightPerformance.player_name == character.name,
            FightPerformance.is_my_character == True,  # noqa: E712
        )
    )
    performances = list(result.scalars().all())

    if not performances:
        return None

    parses = [p.parse_percentile for p in performances if p.parse_percentile is not None]
    dps_values = [p.dps for p in performances if p.dps is not None]
    deaths = [p.deaths for p in performances]

    snapshot = ProgressionSnapshot(
        time=snapshot_time,
        character_id=character.id,
        encounter_id=encounter_id,
        best_parse=max(parses) if parses else None,
        median_parse=median(parses) if parses else None,
        best_dps=max(dps_values) if dps_values else None,
        median_dps=median(dps_values) if dps_values else None,
        kill_count=len(performances),
        avg_deaths=sum(deaths) / len(deaths) if deaths else None,
    )

    return snapshot


async def snapshot_all_characters(
    session,
    snapshot_time: datetime | None = None,
    character_name: str | None = None,
) -> int:
    """Compute progression snapshots for all registered characters.

    For each character, finds all distinct encounter IDs they have kills on,
    then computes a snapshot for each.

    Returns count of snapshots created.
    """
    if snapshot_time is None:
        snapshot_time = datetime.now(UTC)

    # Get characters
    char_query = select(MyCharacter)
    if character_name:
        char_query = char_query.where(MyCharacter.name.ilike(f"%{character_name}%"))

    result = await session.execute(char_query)
    characters = list(result.scalars().all())

    if not characters:
        logger.info("No registered characters found")
        return 0

    count = 0
    for character in characters:
        # Find distinct encounter IDs this character has kill data for
        enc_result = await session.execute(
            select(Fight.encounter_id)
            .distinct()
            .join(FightPerformance, FightPerformance.fight_id == Fight.id)
            .where(
                Fight.kill == True,  # noqa: E712
                FightPerformance.player_name == character.name,
                FightPerformance.is_my_character == True,  # noqa: E712
            )
        )
        encounter_ids = [row[0] for row in enc_result.all()]

        for enc_id in encounter_ids:
            snapshot = await compute_progression_snapshot(
                session,
                character,
                enc_id,
                snapshot_time,
            )
            if snapshot:
                await session.merge(snapshot)
                count += 1
                logger.debug(
                    "Snapshot: %s on encounter %d — %d kills, best parse %.1f%%",
                    character.name,
                    enc_id,
                    snapshot.kill_count,
                    snapshot.best_parse or 0,
                )

    await session.flush()
    logger.info("Created %d progression snapshots", count)
    return count
