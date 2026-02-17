"""REST data endpoints for structured dashboard views."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.models import (
    CharacterFightSummary,
    CharacterInfo,
    CharacterReportSummary,
    DeathEntry,
    EncounterInfo,
    ExecutionBoss,
    FightPlayer,
    IngestRequest,
    IngestResponse,
    ProgressionPoint,
    RaidComparison,
    RaidSummaryFight,
    RegisterCharacterRequest,
    ReportSummary,
    SpecLeaderboardEntry,
    SpeedComparison,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

_session_factory = None


def set_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


async def _get_session() -> AsyncSession:
    if _session_factory is None:
        raise RuntimeError("Data session factory not initialized")
    return _session_factory()


@router.get("/reports", response_model=list[ReportSummary])
async def list_reports():
    session = await _get_session()
    try:
        result = await session.execute(q.REPORTS_LIST)
        rows = result.fetchall()
        return [ReportSummary(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to list reports")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/reports/{report_code}/summary", response_model=list[RaidSummaryFight])
async def report_summary(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(q.RAID_SUMMARY, {"report_code": report_code})
        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No data for report {report_code}")
        return [RaidSummaryFight(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get report summary")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/reports/{report_code}/execution", response_model=list[ExecutionBoss])
async def report_execution(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.RAID_EXECUTION_SUMMARY, {"report_code": report_code}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No kill data for report {report_code}")
        return [ExecutionBoss(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get execution data")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/reports/{report_code}/speed", response_model=list[SpeedComparison])
async def report_speed(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.RAID_VS_TOP_SPEED, {"report_code": report_code}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No kill data for report {report_code}")
        return [SpeedComparison(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get speed data")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}",
    response_model=list[FightPlayer],
)
async def fight_details(report_code: str, fight_id: int):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_DETAILS, {"report_code": report_code, "fight_id": fight_id}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No data for fight {fight_id} in report {report_code}",
            )
        return [FightPlayer(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get fight details")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/reports/{report_code}/deaths", response_model=list[DeathEntry])
async def report_deaths(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(q.REPORT_DEATHS, {"report_code": report_code})
        rows = result.fetchall()
        return [DeathEntry(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get death data")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/compare", response_model=list[RaidComparison])
async def compare_raids(a: str, b: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.COMPARE_TWO_RAIDS, {"report_a": a, "report_b": b}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"No kill data for reports {a} and/or {b}"
            )
        return [RaidComparison(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compare raids")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/progression/{character}", response_model=list[ProgressionPoint])
async def progression(character: str, encounter: str):
    session = await _get_session()
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
    except Exception as e:
        logger.exception("Failed to get progression data")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/leaderboard/{encounter}", response_model=list[SpecLeaderboardEntry])
async def spec_leaderboard(encounter: str):
    session = await _get_session()
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
    finally:
        await session.close()


@router.get("/encounters", response_model=list[EncounterInfo])
async def list_encounters():
    session = await _get_session()
    try:
        result = await session.execute(q.ENCOUNTERS_LIST)
        rows = result.fetchall()
        return [EncounterInfo(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to list encounters")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/characters", response_model=list[CharacterInfo])
async def list_characters():
    session = await _get_session()
    try:
        result = await session.execute(q.CHARACTERS_LIST)
        rows = result.fetchall()
        return [CharacterInfo(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to list characters")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.post("/characters", response_model=CharacterInfo)
async def create_character(req: RegisterCharacterRequest):
    from shukketsu.pipeline.characters import register_character

    session = await _get_session()
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
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to register character")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/characters/{character_name}/reports",
    response_model=list[CharacterReportSummary],
)
async def character_reports(character_name: str):
    session = await _get_session()
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
    except Exception as e:
        logger.exception("Failed to get character reports")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/characters/{character_name}/reports/{report_code}",
    response_model=list[CharacterFightSummary],
)
async def character_report_detail(character_name: str, report_code: str):
    session = await _get_session()
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
    except Exception as e:
        logger.exception("Failed to get character report detail")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_report_endpoint(req: IngestRequest):
    from sqlalchemy import select

    from shukketsu.config import get_settings
    from shukketsu.db.models import MyCharacter
    from shukketsu.pipeline.ingest import ingest_report
    from shukketsu.wcl.auth import WCLAuth
    from shukketsu.wcl.client import WCLClient
    from shukketsu.wcl.rate_limiter import RateLimiter

    settings = get_settings()
    if not settings.wcl.client_id:
        raise HTTPException(
            status_code=503, detail="WCL credentials not configured"
        )

    session = await _get_session()
    try:
        # Get registered character names for is_my_character flagging
        chars = await session.execute(select(MyCharacter.name))
        my_names = {r[0] for r in chars}

        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with WCLClient(auth, RateLimiter()) as wcl:
            result = await ingest_report(
                wcl, session, req.report_code, my_names,
            )
        await session.commit()
        logger.info(
            "Ingested report %s: %d fights, %d performances",
            req.report_code, result.fights, result.performances,
        )
        return IngestResponse(
            report_code=req.report_code,
            fights=result.fights,
            performances=result.performances,
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to ingest report %s", req.report_code)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()
