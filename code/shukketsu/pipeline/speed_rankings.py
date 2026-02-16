"""Speed rankings ingestion pipeline.

Fetches fightRankings (speed metric) from the WCL API for each encounter
and persists them to the speed_rankings table.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from shukketsu.db.models import SpeedRanking

logger = logging.getLogger(__name__)

MAX_SPEED_RANKINGS = 100


def parse_speed_rankings(raw_data, encounter_id: int) -> list[SpeedRanking]:
    """Parse WCL fightRankings JSON into SpeedRanking ORM objects.

    raw_data: The fightRankings value from the WCL response.
    Could be a dict or a JSON string (WCL returns it as a JSON scalar).
    """
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)

    if raw_data is None:
        return []

    rankings_list = raw_data.get("rankings", [])
    result = []

    for i, entry in enumerate(rankings_list[:MAX_SPEED_RANKINGS], start=1):
        report = entry.get("report") or {}
        guild = report.get("guild") or {}

        result.append(
            SpeedRanking(
                encounter_id=encounter_id,
                rank_position=i,
                report_code=report.get("code", ""),
                fight_id=entry.get("fightID", 0),
                duration_ms=entry.get("duration", 0),
                guild_name=guild.get("name"),
            )
        )

    return result


@dataclass
class SpeedRankingsResult:
    """Aggregated result from a speed rankings ingestion run."""

    fetched: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


async def fetch_speed_rankings_for_encounter(
    wcl,
    session,
    encounter_id: int,
) -> int:
    """Fetch speed rankings for one encounter.

    Deletes existing rows for this encounter, inserts fresh data.
    Returns count of rankings inserted.
    """
    from shukketsu.wcl.queries import SPEED_RANKINGS

    data = await wcl.query(
        SPEED_RANKINGS.replace(
            "RATE_LIMIT",
            "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }",
        ),
        variables={
            "encounterID": encounter_id,
            "page": 1,
        },
    )

    raw_rankings = data["worldData"]["encounter"]["fightRankings"]
    rankings = parse_speed_rankings(raw_rankings, encounter_id)

    # Delete existing rows for this encounter
    await session.execute(
        delete(SpeedRanking).where(
            SpeedRanking.encounter_id == encounter_id,
        )
    )

    for r in rankings:
        session.add(r)

    return len(rankings)


async def ingest_all_speed_rankings(
    wcl,
    session,
    encounter_ids: list[int],
    force: bool = False,
    stale_hours: int = 24,
) -> SpeedRankingsResult:
    """Fetch speed rankings for all encounters.

    Commits after each encounter. Skips recently-fetched encounters
    unless force=True.
    """
    result = SpeedRankingsResult()
    total = len(encounter_ids)

    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    for i, enc_id in enumerate(encounter_ids, start=1):
        try:
            # Check staleness (unless force)
            if not force:
                existing = await session.execute(
                    select(func.max(SpeedRanking.fetched_at)).where(
                        SpeedRanking.encounter_id == enc_id,
                    )
                )
                last_fetched = existing.scalar_one_or_none()
                if last_fetched and last_fetched.replace(tzinfo=UTC) > cutoff:
                    result.skipped += 1
                    logger.debug(
                        "[%d/%d] Skipping encounter %d — fresh",
                        i, total, enc_id,
                    )
                    continue

            count = await fetch_speed_rankings_for_encounter(wcl, session, enc_id)
            result.fetched += 1
            logger.info(
                "[%d/%d] Fetched %d speed rankings for encounter %d",
                i, total, count, enc_id,
            )
        except Exception as e:
            error_msg = f"encounter {enc_id}: {e}"
            result.errors.append(error_msg)
            logger.error("[%d/%d] Error: %s", i, total, error_msg)

        # Commit after each encounter
        await session.commit()

    return result
