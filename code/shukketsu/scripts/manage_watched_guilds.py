"""CLI script to manage watched guilds for benchmark tracking."""

import argparse
import asyncio
import logging

from sqlalchemy import select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import WatchedGuild

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage watched guilds for benchmark tracking"
    )
    parser.add_argument(
        "--add", metavar="NAME", help="Add a watched guild"
    )
    parser.add_argument(
        "--guild-id", type=int, help="WCL guild ID (required with --add)"
    )
    parser.add_argument(
        "--server", help="Server slug (required with --add)"
    )
    parser.add_argument(
        "--region", default="US", help="Server region (default: US)"
    )
    parser.add_argument(
        "--list", action="store_true", dest="list_guilds",
        help="List all watched guilds",
    )
    parser.add_argument(
        "--remove", metavar="NAME", help="Remove a watched guild by name"
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    if args.add:
        if not args.guild_id:
            logger.error("--guild-id is required with --add")
            await engine.dispose()
            return
        if not args.server:
            logger.error("--server is required with --add")
            await engine.dispose()
            return

        async with session_factory() as session:
            guild = WatchedGuild(
                guild_name=args.add,
                wcl_guild_id=args.guild_id,
                server_slug=args.server,
                server_region=args.region,
            )
            session.add(guild)
            await session.commit()
            logger.info(
                "Added watched guild: %s (id=%d, %s-%s)",
                args.add, args.guild_id, args.server, args.region,
            )

    elif args.remove:
        async with session_factory() as session:
            stmt = select(WatchedGuild).where(
                WatchedGuild.guild_name.ilike(f"%{args.remove}%")
            )
            result = await session.execute(stmt)
            guilds = list(result.scalars().all())
            if not guilds:
                logger.error("No watched guild found matching '%s'", args.remove)
            else:
                for guild in guilds:
                    await session.delete(guild)
                    logger.info("Removed watched guild: %s", guild.guild_name)
                await session.commit()

    elif args.list_guilds:
        async with session_factory() as session:
            stmt = select(WatchedGuild).order_by(WatchedGuild.guild_name)
            result = await session.execute(stmt)
            guilds = list(result.scalars().all())
            if not guilds:
                logger.info("No watched guilds configured")
            else:
                logger.info("Watched guilds (%d):", len(guilds))
                for g in guilds:
                    logger.info(
                        "  %s (id=%d, %s-%s, active=%s)",
                        g.guild_name, g.wcl_guild_id,
                        g.server_slug, g.server_region, g.is_active,
                    )

    else:
        logger.info(
            "No action specified. Use --add, --remove, or --list."
        )

    await engine.dispose()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
