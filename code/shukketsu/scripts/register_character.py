import argparse
import asyncio
import logging

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.pipeline.characters import list_characters, register_character

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a tracked character")
    parser.add_argument("--name", help="Character name")
    parser.add_argument("--server", help="Server slug (e.g., faerlina)")
    parser.add_argument("--region", help="Server region (e.g., us)")
    parser.add_argument(
        "--class-name", dest="class_name", help="Character class (e.g., Rogue)"
    )
    parser.add_argument("--spec", help="Specialization (e.g., Combat)")
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_chars",
        help="List all registered characters",
    )
    return parser.parse_args(argv)


async def run(
    name: str | None = None,
    server: str | None = None,
    region: str | None = None,
    class_name: str | None = None,
    spec: str | None = None,
    list_chars: bool = False,
) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        if list_chars:
            characters = await list_characters(session)
            if not characters:
                logger.info("No characters registered")
            for c in characters:
                logger.info(
                    "  %s - %s-%s (%s %s)",
                    c.id,
                    c.name,
                    c.server_slug,
                    c.character_class,
                    c.spec,
                )
        elif name and server and region and class_name and spec:
            char = await register_character(
                session,
                name,
                server,
                region,
                class_name,
                spec,
            )
            await session.commit()
            logger.info("Registered: %s (id=%s)", char.name, char.id)
        else:
            logger.error(
                "Provide --name, --server, --region, --class-name, --spec "
                "for registration, or --list to show characters"
            )

    await engine.dispose()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run(
            name=args.name,
            server=args.server,
            region=args.region,
            class_name=args.class_name,
            spec=args.spec,
            list_chars=args.list_chars,
        )
    )


if __name__ == "__main__":
    main()
