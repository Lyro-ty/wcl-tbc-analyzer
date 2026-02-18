"""Character roster, progression, profile, and regression endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import get_db
from shukketsu.api.models import (
    CharacterFightSummary,
    CharacterInfo,
    CharacterProfile,
    CharacterRecentParse,
    CharacterReportSummary,
    PersonalBestEntry,
    ProgressionPoint,
    RegisterCharacterRequest,
    RegressionEntry,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/characters", response_model=list[CharacterInfo])
async def list_characters(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(q.CHARACTERS_LIST)
        rows = result.fetchall()
        return [CharacterInfo(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to list characters")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/characters", response_model=CharacterInfo)
async def create_character(
    req: RegisterCharacterRequest, session: AsyncSession = Depends(get_db),
):
    from shukketsu.pipeline.characters import register_character

    try:
        character = await register_character(
            session,
            name=req.name,
            server_slug=req.server_slug,
            server_region=req.server_region,
            character_class=req.character_class,
            spec=req.spec,
        )
        await session.commit()
        return CharacterInfo(
            id=character.id,
            name=character.name,
            server_slug=character.server_slug,
            server_region=character.server_region,
            character_class=character.character_class,
            spec=character.spec,
        )
    except Exception:
        await session.rollback()
        logger.exception("Failed to register character")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/characters/{character_name}/reports",
    response_model=list[CharacterReportSummary],
)
async def character_reports(
    character_name: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.CHARACTER_REPORTS, {"character_name": character_name}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No reports found for character {character_name}",
            )
        return [CharacterReportSummary(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get character reports")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/characters/{character_name}/reports/{report_code}",
    response_model=list[CharacterFightSummary],
)
async def character_report_detail(
    character_name: str, report_code: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.CHARACTER_REPORT_DETAIL,
            {"character_name": character_name, "report_code": report_code},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No data for {character_name} in report {report_code}",
            )
        return [CharacterFightSummary(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get character report detail")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/characters/{character_name}/profile",
    response_model=CharacterProfile,
)
async def character_profile(
    character_name: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.CHARACTER_PROFILE, {"character_name": character_name}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Character {character_name} not found",
            )
        return CharacterProfile(**dict(row._mapping))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get character profile")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/characters/{character_name}/recent-parses",
    response_model=list[CharacterRecentParse],
)
async def character_recent_parses(
    character_name: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.CHARACTER_RECENT_PARSES, {"character_name": character_name}
        )
        rows = result.fetchall()
        return [CharacterRecentParse(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to get recent parses")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/characters/{character_name}/personal-bests",
    response_model=list[PersonalBestEntry],
)
async def character_personal_bests(
    character_name: str, encounter: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """Get a character's personal records per encounter."""
    try:
        if encounter:
            result = await session.execute(
                q.PERSONAL_BESTS_BY_ENCOUNTER,
                {"player_name": f"%{character_name}%",
                 "encounter_name": f"%{encounter}%"},
            )
        else:
            result = await session.execute(
                q.PERSONAL_BESTS,
                {"player_name": f"%{character_name}%"},
            )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No personal bests found for {character_name}",
            )
        return [PersonalBestEntry(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get personal bests")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/progression/{character}", response_model=list[ProgressionPoint])
async def progression(
    character: str, encounter: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.PROGRESSION,
            {"character_name": f"%{character}%", "encounter_name": f"%{encounter}%"},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No progression data for {character} on {encounter}",
            )
        return [
            ProgressionPoint(
                time=r.time.isoformat(),
                best_parse=r.best_parse,
                median_parse=r.median_parse,
                best_dps=r.best_dps,
                median_dps=r.median_dps,
                kill_count=r.kill_count,
                avg_deaths=r.avg_deaths,
                encounter_name=r.encounter_name,
                character_name=r.character_name,
            )
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get progression data")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/regressions", response_model=list[RegressionEntry])
async def get_regressions_endpoint(
    player: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """Get performance regressions/improvements for tracked characters."""
    try:
        if player:
            result = await session.execute(
                q.REGRESSION_CHECK_PLAYER,
                {"player_name": f"%{player}%"},
            )
        else:
            result = await session.execute(q.REGRESSION_CHECK)
        rows = result.fetchall()
        return [RegressionEntry(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to get regressions")
        raise HTTPException(status_code=500, detail="Internal server error") from None
