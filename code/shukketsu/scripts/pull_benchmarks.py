"""CLI script to pull top guild reports and compute encounter benchmarks."""

import argparse
import asyncio
import logging

from sqlalchemy import select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import Encounter
from shukketsu.pipeline.benchmarks import run_benchmark_pipeline
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull top guild reports and compute benchmarks"
    )
    parser.add_argument(
        "--encounter", help="Filter by encounter name"
    )
    parser.add_argument(
        "--zone-id", type=int, help="Filter by zone ID"
    )
    parser.add_argument(
        "--max-reports",
        type=int,
        default=10,
        help="Max reports per encounter (default: 10)",
    )
    parser.add_argument(
        "--compute-only",
        action="store_true",
        help="Skip ingestion, recompute from existing data",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest already-tracked reports",
    )
    return parser.parse_args(argv)


async def run(
    encounter: str | None = None,
    zone_id: int | None = None,
    max_reports: int = 10,
    compute_only: bool = False,
    force: bool = False,
) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    # Resolve encounter filter to encounter_id
    encounter_id = None
    if encounter:
        async with session_factory() as session:
            query = select(Encounter).where(
                Encounter.name.ilike(f"%{encounter}%")
            )
            db_result = await session.execute(query)
            matches = list(db_result.scalars().all())

        if not matches:
            logger.error("No encounters found matching '%s'", encounter)
            await engine.dispose()
            return

        if len(matches) > 1:
            logger.warning(
                "Multiple encounters match '%s', using first: %s",
                encounter, matches[0].name,
            )
        encounter_id = matches[0].id
        logger.info("Resolved encounter: %s (id=%d)", matches[0].name, encounter_id)

    if zone_id:
        logger.info("Filtering to zone_id=%d", zone_id)

    if compute_only:
        logger.info("Compute-only mode — skipping report discovery and ingestion")
        async with session_factory() as session:
            result = await run_benchmark_pipeline(
                None, session, encounter_id=encounter_id,
                max_reports_per_encounter=max_reports,
                compute_only=True, force=force,
            )
        await engine.dispose()
        logger.info(
            "Done: computed=%d, errors=%d",
            result.computed, len(result.errors),
        )
        if result.errors:
            for err in result.errors:
                logger.error("  %s", err)
        return

    auth = WCLAuth(
        settings.wcl.client_id,
        settings.wcl.client_secret.get_secret_value(),
        settings.wcl.oauth_url,
    )
    async with (
        WCLClient(auth, RateLimiter(), api_url=settings.wcl.api_url) as wcl,
        session_factory() as session,
    ):
        result = await run_benchmark_pipeline(
            wcl, session, encounter_id=encounter_id,
            max_reports_per_encounter=max_reports,
            compute_only=False, force=force,
        )

    await engine.dispose()
    logger.info(
        "Done: discovered=%d, ingested=%d, computed=%d, errors=%d",
        result.discovered, result.ingested, result.computed, len(result.errors),
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
            max_reports=args.max_reports,
            compute_only=args.compute_only,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
