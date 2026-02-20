import argparse
import asyncio
import logging

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.pipeline.ingest import ingest_report
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull WCL report data")
    parser.add_argument("--report-code", required=True, help="WCL report code")
    parser.add_argument(
        "--with-tables", action="store_true",
        help="Also fetch ability breakdowns and buff uptimes",
    )
    parser.add_argument(
        "--with-events", action="store_true",
        help="Also fetch event data (deaths, cast metrics, cooldowns)",
    )
    return parser.parse_args(argv)


async def run(
    report_code: str, *, with_tables: bool = False, with_events: bool = False,
) -> None:
    from shukketsu.pipeline.progression import snapshot_all_characters

    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    auth = WCLAuth(
        settings.wcl.client_id,
        settings.wcl.client_secret.get_secret_value(),
        settings.wcl.oauth_url,
    )
    async with WCLClient(auth, RateLimiter(), api_url=settings.wcl.api_url) as wcl:
        # Ingest in an atomic transaction
        async with session_factory() as session, session.begin():
            result = await ingest_report(
                wcl, session, report_code,
                ingest_tables=with_tables, ingest_events=with_events,
            )

        # Snapshot progression in a separate transaction after successful commit
        try:
            async with session_factory() as session, session.begin():
                snapshot_count = await snapshot_all_characters(session)
            logger.info("Snapshotted %d progression entries", snapshot_count)
        except Exception:
            logger.exception(
                "Failed to snapshot progression after ingest of %s",
                report_code,
            )

    await engine.dispose()
    logger.info(
        "Ingested report %s: %d fights, %d performances, %d table rows, "
        "%d event rows",
        report_code, result.fights, result.performances,
        result.table_rows, result.event_rows,
    )


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(
        args.report_code, with_tables=args.with_tables, with_events=args.with_events,
    ))


if __name__ == "__main__":
    main()
