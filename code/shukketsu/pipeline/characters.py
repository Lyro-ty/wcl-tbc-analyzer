import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.db.models import FightPerformance, MyCharacter

logger = logging.getLogger(__name__)


async def register_character(
    session: AsyncSession,
    name: str,
    server_slug: str,
    server_region: str,
    character_class: str,
    spec: str,
) -> MyCharacter:
    """Register or update a tracked character.

    Uses the unique constraint (name, server_slug, server_region) to determine
    if this is a new registration or an update.
    After registration, retroactively marks matching fight_performances.
    """
    # Check for existing character
    result = await session.execute(
        select(MyCharacter).where(
            MyCharacter.name == name,
            MyCharacter.server_slug == server_slug,
            MyCharacter.server_region == server_region,
        )
    )
    character = result.scalar_one_or_none()

    if character:
        character.character_class = character_class
        character.spec = spec
        logger.info("Updated character %s-%s", name, server_slug)
    else:
        character = MyCharacter(
            name=name,
            server_slug=server_slug,
            server_region=server_region,
            character_class=character_class,
            spec=spec,
        )
        session.add(character)
        logger.info("Registered new character %s-%s", name, server_slug)

    await session.flush()

    # Retroactively mark fight_performances (case-insensitive)
    await session.execute(
        update(FightPerformance)
        .where(func.lower(FightPerformance.player_name) == name.lower())
        .where(FightPerformance.is_my_character == False)  # noqa: E712
        .values(is_my_character=True)
    )

    return character


async def list_characters(session: AsyncSession) -> list[MyCharacter]:
    """Return all registered characters."""
    result = await session.execute(
        select(MyCharacter).order_by(MyCharacter.name)
    )
    return list(result.scalars().all())
