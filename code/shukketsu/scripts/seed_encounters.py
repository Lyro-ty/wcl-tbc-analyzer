"""CLI script to seed encounter data from WCL API."""

import argparse
import asyncio
import logging

from sqlalchemy import select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import Encounter
from shukketsu.pipeline.seeds import discover_and_seed_encounters, seed_encounters_from_list
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed encounter data from WCL API")
    parser.add_argument(
        "--zone-ids",
        help="Comma-separated WCL zone IDs to discover encounters from",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Re-seed encounters already in DB (fix stubs with zone_id=0)",
    )
    return parser.parse_args(argv)


async def run(zone_ids: list[int] | None = None, from_db: bool = False) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    if zone_ids:
        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with (
            WCLClient(auth, RateLimiter(), api_url=settings.wcl.api_url) as wcl,
            session_factory() as session,
        ):
            encounters = await discover_and_seed_encounters(wcl, session, zone_ids)
            await session.commit()
        logger.info("Discovered and seeded %d encounters", len(encounters))
    elif from_db:
        async with session_factory() as session:
            result = await session.execute(select(Encounter))
            existing = result.scalars().all()
            enc_list = [
                {
                    "id": e.id,
                    "name": e.name,
                    "zone_id": e.zone_id,
                    "zone_name": e.zone_name,
                    "difficulty": e.difficulty,
                }
                for e in existing
            ]
            count = await seed_encounters_from_list(session, enc_list)
            await session.commit()
        logger.info("Re-seeded %d encounters from DB", count)
    else:
        logger.error("Specify --zone-ids or --from-db")

    await engine.dispose()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    zone_ids = None
    if args.zone_ids:
        zone_ids = [int(z.strip()) for z in args.zone_ids.split(",")]
    asyncio.run(run(zone_ids=zone_ids, from_db=args.from_db))


if __name__ == "__main__":
    main()
