"""Backfill event data (deaths, cast metrics, cooldowns) for existing reports."""

import argparse
import asyncio
import logging

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.pipeline.event_data import ingest_event_data_for_report
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill event data (deaths, cast metrics, cooldowns) for existing reports",
    )
    parser.add_argument("--report-code", required=True, help="WCL report code")
    return parser.parse_args(argv)


async def run(report_code: str) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    auth = WCLAuth(
        settings.wcl.client_id,
        settings.wcl.client_secret.get_secret_value(),
        settings.wcl.oauth_url,
    )
    async with WCLClient(auth, RateLimiter()) as wcl, session_factory() as session:
        total = await ingest_event_data_for_report(wcl, session, report_code)
        await session.commit()
    await engine.dispose()
    logger.info("Backfilled %d event data rows for report %s", total, report_code)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.report_code))


if __name__ == "__main__":
    main()
