"""CLI script to pull top rankings from WCL for all encounter x spec combos."""

import argparse
import asyncio
import logging

from sqlalchemy import select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import Encounter
from shukketsu.pipeline.constants import TBC_SPECS
from shukketsu.pipeline.rankings import ingest_all_rankings
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull top rankings from WCL")
    parser.add_argument(
        "--encounter", help="Filter encounters by name substring"
    )
    parser.add_argument(
        "--zone-id", type=int, help="Filter encounters by zone ID"
    )
    parser.add_argument("--class-name", help="Filter by class name")
    parser.add_argument("--spec-name", help="Filter by spec name")
    parser.add_argument(
        "--include-hps",
        action="store_true",
        help="Also fetch HPS rankings for healer specs",
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
    class_name: str | None = None,
    spec_name: str | None = None,
    include_hps: bool = False,
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

    # Build spec filter
    specs = list(TBC_SPECS)
    if class_name:
        specs = [s for s in specs if s.class_name.lower() == class_name.lower()]
    if spec_name:
        specs = [s for s in specs if s.spec_name.lower() == spec_name.lower()]

    if not specs:
        logger.error("No specs found matching filters")
        await engine.dispose()
        return

    # Estimate API calls
    dps_calls = len(encounter_ids) * len(specs)
    hps_calls = (
        len(encounter_ids) * len([s for s in specs if s.role == "healer"])
        if include_hps
        else 0
    )
    total_calls = dps_calls + hps_calls

    logger.info(
        "Encounters: %d, Specs: %d, Estimated API calls: %d (DPS: %d, HPS: %d)",
        len(encounter_ids),
        len(specs),
        total_calls,
        dps_calls,
        hps_calls,
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
    ):
        result = await ingest_all_rankings(
            wcl,
            session,
            encounter_ids,
            specs,
            include_hps=include_hps,
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
            class_name=args.class_name,
            spec_name=args.spec_name,
            include_hps=args.include_hps,
            force=args.force,
            stale_hours=args.stale_hours,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
