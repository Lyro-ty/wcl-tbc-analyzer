"""Rankings, speed rankings, leaderboard, and encounter list endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import cooldown, get_db
from shukketsu.api.models import (
    EncounterInfo,
    RankingsRefreshResponse,
    SpecLeaderboardEntry,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/encounters", response_model=list[EncounterInfo])
async def list_encounters(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(q.ENCOUNTERS_LIST)
        rows = result.fetchall()
        return [EncounterInfo(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to list encounters")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/leaderboard/{encounter}", response_model=list[SpecLeaderboardEntry])
async def spec_leaderboard(
    encounter: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.SPEC_LEADERBOARD, {"encounter_name": f"%{encounter}%"}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"No leaderboard data for {encounter}"
            )
        return [SpecLeaderboardEntry(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get leaderboard")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/rankings/refresh",
    response_model=RankingsRefreshResponse,
    dependencies=[cooldown("rankings_refresh", 300)],
)
async def refresh_rankings(
    zone_id: int | None = None, force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from shukketsu.config import get_settings
    from shukketsu.db.models import Encounter
    from shukketsu.pipeline.constants import TBC_SPECS
    from shukketsu.pipeline.rankings import ingest_all_rankings
    from shukketsu.wcl.auth import WCLAuth
    from shukketsu.wcl.client import WCLClient
    from shukketsu.wcl.rate_limiter import RateLimiter

    settings = get_settings()
    if not settings.wcl.client_id:
        raise HTTPException(
            status_code=503, detail="WCL credentials not configured"
        )

    try:
        stmt = select(Encounter.id)
        if zone_id is not None:
            stmt = stmt.where(Encounter.zone_id == zone_id)
        rows = await session.execute(stmt)
        encounter_ids = [r[0] for r in rows]
        if not encounter_ids:
            raise HTTPException(
                status_code=404, detail="No encounters found"
            )

        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with WCLClient(auth, RateLimiter()) as wcl:
            result = await ingest_all_rankings(
                wcl, session, encounter_ids, list(TBC_SPECS), force=force,
            )
        logger.info(
            "Rankings refresh: %d fetched, %d skipped, %d errors",
            result.fetched, result.skipped, len(result.errors),
        )
        return RankingsRefreshResponse(
            fetched=result.fetched,
            skipped=result.skipped,
            errors=result.errors,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to refresh rankings")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/speed-rankings/refresh",
    response_model=RankingsRefreshResponse,
    dependencies=[cooldown("speed_rankings_refresh", 300)],
)
async def refresh_speed_rankings(
    zone_id: int | None = None, force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from shukketsu.config import get_settings
    from shukketsu.db.models import Encounter
    from shukketsu.pipeline.speed_rankings import ingest_all_speed_rankings
    from shukketsu.wcl.auth import WCLAuth
    from shukketsu.wcl.client import WCLClient
    from shukketsu.wcl.rate_limiter import RateLimiter

    settings = get_settings()
    if not settings.wcl.client_id:
        raise HTTPException(
            status_code=503, detail="WCL credentials not configured"
        )

    try:
        stmt = select(Encounter.id)
        if zone_id is not None:
            stmt = stmt.where(Encounter.zone_id == zone_id)
        rows = await session.execute(stmt)
        encounter_ids = [r[0] for r in rows]
        if not encounter_ids:
            raise HTTPException(
                status_code=404, detail="No encounters found"
            )

        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with WCLClient(auth, RateLimiter()) as wcl:
            result = await ingest_all_speed_rankings(
                wcl, session, encounter_ids, force=force,
            )
        logger.info(
            "Speed rankings refresh: %d fetched, %d skipped, %d errors",
            result.fetched, result.skipped, len(result.errors),
        )
        return RankingsRefreshResponse(
            fetched=result.fetched,
            skipped=result.skipped,
            errors=result.errors,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to refresh speed rankings")
        raise HTTPException(status_code=500, detail=str(e)) from e
