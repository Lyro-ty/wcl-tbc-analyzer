import argparse
import asyncio
import logging

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.pipeline.progression import snapshot_all_characters

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute progression snapshots")
    parser.add_argument("--character", help="Filter by character name (optional)")
    return parser.parse_args(argv)


async def run(character: str | None = None) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        count = await snapshot_all_characters(session, character_name=character)
        await session.commit()

    await engine.dispose()
    logger.info("Created %d progression snapshots", count)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(character=args.character))


if __name__ == "__main__":
    main()
