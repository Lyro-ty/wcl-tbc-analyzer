"""CLI script to pull speed (kill time) rankings from WCL for each encounter."""

import argparse
import asyncio
import logging

from sqlalchemy import select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import Encounter
from shukketsu.pipeline.speed_rankings import ingest_all_speed_rankings
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull speed rankings from WCL")
    parser.add_argument(
        "--encounter", help="Filter encounters by name substring"
    )
    parser.add_argument(
        "--zone-id", type=int, help="Filter encounters by zone ID"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if data is fresh",
    )
    parser.add_argument(
        "--stale-hours",
        type=int,
        default=24,
        help="Hours before data is considered stale (default: 24)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count API calls without executing",
    )
    return parser.parse_args(argv)


async def run(
    encounter: str | None = None,
    zone_id: int | None = None,
    force: bool = False,
    stale_hours: int = 24,
    dry_run: bool = False,
) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    # Build encounter filter
    async with session_factory() as session:
        query = select(Encounter)
        if encounter:
            query = query.where(Encounter.name.ilike(f"%{encounter}%"))
        if zone_id:
            query = query.where(Encounter.zone_id == zone_id)
        db_result = await session.execute(query)
        encounters = list(db_result.scalars().all())

    if not encounters:
        logger.error("No encounters found matching filters")
        await engine.dispose()
        return

    encounter_ids = [e.id for e in encounters]

    logger.info(
        "Encounters: %d, Estimated API calls: %d",
        len(encounter_ids),
        len(encounter_ids),
    )

    if dry_run:
        for e in encounters:
            logger.info("  %d: %s (%s)", e.id, e.name, e.zone_name)
        logger.info("Dry run — no API calls made")
        await engine.dispose()
        return

    auth = WCLAuth(
        settings.wcl.client_id,
        settings.wcl.client_secret.get_secret_value(),
        settings.wcl.oauth_url,
    )
    async with (
        WCLClient(auth, RateLimiter()) as wcl,
        session_factory() as session,
        session.begin(),
    ):
        result = await ingest_all_speed_rankings(
            wcl,
            session,
            encounter_ids,
            force=force,
            stale_hours=stale_hours,
        )

    await engine.dispose()
    logger.info(
        "Done: fetched=%d, skipped=%d, errors=%d",
        result.fetched,
        result.skipped,
        len(result.errors),
    )
    if result.errors:
        for err in result.errors:
            logger.error("  %s", err)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run(
            encounter=args.encounter,
            zone_id=args.zone_id,
            force=args.force,
            stale_hours=args.stale_hours,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
