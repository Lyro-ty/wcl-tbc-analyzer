"""REST data endpoints for structured dashboard views."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.models import (
    AbilitiesAvailable,
    AbilityMetricResponse,
    BuffUptimeResponse,
    CancelledCastResponse,
    CastEventResponse,
    CastMetricResponse,
    CharacterFightSummary,
    CharacterInfo,
    CharacterProfile,
    CharacterRecentParse,
    CharacterReportSummary,
    ConsumableItem,
    ConsumablePlayerEntry,
    CooldownUsageResponse,
    CooldownWindowResponse,
    DashboardStats,
    DeathDetailResponse,
    DeathEntry,
    DotRefreshResponse,
    EncounterInfo,
    EventDataResponse,
    EventsAvailable,
    ExecutionBoss,
    FightPlayer,
    GearChangeEntry,
    GearSlotEntry,
    IngestRequest,
    IngestResponse,
    OverhealAbility,
    OverhealResponse,
    PersonalBestEntry,
    PhaseAnalysis,
    PhaseInfo,
    PhaseMetricResponse,
    PhasePlayerPerformance,
    ProgressionPoint,
    RaidComparison,
    RaidNightSummary,
    RaidSummaryFight,
    RankingsRefreshResponse,
    RecentReportSummary,
    RegisterCharacterRequest,
    RegressionEntry,
    ReportSummary,
    ResourceSnapshotResponse,
    RotationScoreResponse,
    SpecLeaderboardEntry,
    SpeedComparison,
    TableDataResponse,
    TrinketProcResponse,
    WipeProgressionAttempt,
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


@router.get(
    "/reports/{report_code}/fights/{fight_id}/abilities",
    response_model=list[AbilityMetricResponse],
)
async def fight_abilities(report_code: str, fight_id: int):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_ABILITIES, {"report_code": report_code, "fight_id": fight_id}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No ability data for fight {fight_id} in report {report_code}",
            )
        return [AbilityMetricResponse(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get fight abilities")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/abilities/{player}",
    response_model=list[AbilityMetricResponse],
)
async def player_abilities(report_code: str, fight_id: int, player: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_ABILITIES_PLAYER,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No ability data for {player} in fight {fight_id}",
            )
        return [AbilityMetricResponse(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get player abilities")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/buffs",
    response_model=list[BuffUptimeResponse],
)
async def fight_buffs(report_code: str, fight_id: int):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_BUFFS, {"report_code": report_code, "fight_id": fight_id}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No buff data for fight {fight_id} in report {report_code}",
            )
        return [BuffUptimeResponse(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get fight buffs")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/buffs/{player}",
    response_model=list[BuffUptimeResponse],
)
async def player_buffs(report_code: str, fight_id: int, player: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_BUFFS_PLAYER,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No buff data for {player} in fight {fight_id}",
            )
        return [BuffUptimeResponse(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get player buffs")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/abilities-available",
    response_model=AbilitiesAvailable,
)
async def abilities_available(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.TABLE_DATA_EXISTS, {"report_code": report_code}
        )
        row = result.fetchone()
        return AbilitiesAvailable(has_data=row.has_data if row else False)
    except Exception as e:
        logger.exception("Failed to check abilities availability")
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
                ingest_tables=req.with_tables,
                ingest_events=req.with_events,
            )
        await session.commit()
        logger.info(
            "Ingested report %s: %d fights, %d performances, %d table rows, %d event rows",
            req.report_code, result.fights, result.performances,
            result.table_rows, result.event_rows,
        )
        return IngestResponse(
            report_code=req.report_code,
            fights=result.fights,
            performances=result.performances,
            table_rows=result.table_rows,
            event_rows=result.event_rows,
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to ingest report %s", req.report_code)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.post(
    "/reports/{report_code}/table-data",
    response_model=TableDataResponse,
)
async def fetch_table_data(report_code: str):
    from shukketsu.config import get_settings
    from shukketsu.pipeline.table_data import ingest_table_data_for_report
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
        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with WCLClient(auth, RateLimiter()) as wcl:
            rows = await ingest_table_data_for_report(wcl, session, report_code)
        await session.commit()
        logger.info("Fetched table data for %s: %d rows", report_code, rows)
        return TableDataResponse(report_code=report_code, table_rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to fetch table data for %s", report_code)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.post(
    "/reports/{report_code}/event-data",
    response_model=EventDataResponse,
)
async def fetch_event_data(report_code: str):
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
        chars = await session.execute(select(MyCharacter.name))
        my_names = {r[0] for r in chars}

        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with WCLClient(auth, RateLimiter()) as wcl:
            result = await ingest_report(
                wcl, session, report_code, my_names,
                ingest_events=True,
            )
        await session.commit()
        logger.info(
            "Fetched event data for %s: %d event rows",
            report_code, result.event_rows,
        )
        return EventDataResponse(
            report_code=report_code, event_rows=result.event_rows,
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to fetch event data for %s", report_code)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.post("/rankings/refresh", response_model=RankingsRefreshResponse)
async def refresh_rankings(zone_id: int | None = None, force: bool = False):
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

    session = await _get_session()
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
    finally:
        await session.close()


@router.post("/speed-rankings/refresh", response_model=RankingsRefreshResponse)
async def refresh_speed_rankings(zone_id: int | None = None, force: bool = False):
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

    session = await _get_session()
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
    finally:
        await session.close()


@router.get(
    "/characters/{character_name}/profile",
    response_model=CharacterProfile,
)
async def character_profile(character_name: str):
    session = await _get_session()
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
    except Exception as e:
        logger.exception("Failed to get character profile")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/characters/{character_name}/recent-parses",
    response_model=list[CharacterRecentParse],
)
async def character_recent_parses(character_name: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.CHARACTER_RECENT_PARSES, {"character_name": character_name}
        )
        rows = result.fetchall()
        return [CharacterRecentParse(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get recent parses")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/characters/{character_name}/personal-bests",
    response_model=list[PersonalBestEntry],
)
async def character_personal_bests(
    character_name: str, encounter: str | None = None,
):
    """Get a character's personal records per encounter."""
    session = await _get_session()
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
    except Exception as e:
        logger.exception("Failed to get personal bests")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/deaths",
    response_model=list[DeathDetailResponse],
)
async def fight_deaths(report_code: str, fight_id: int):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_DEATHS, {"report_code": report_code, "fight_id": fight_id}
        )
        rows = result.fetchall()
        return [DeathDetailResponse(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get fight deaths")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cast-metrics/{player}",
    response_model=CastMetricResponse | None,
)
async def fight_cast_metrics(report_code: str, fight_id: int, player: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_CAST_METRICS,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        row = result.fetchone()
        if not row:
            return None
        return CastMetricResponse(**dict(row._mapping))
    except Exception as e:
        logger.exception("Failed to get cast metrics")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cooldowns/{player}",
    response_model=list[CooldownUsageResponse],
)
async def fight_cooldowns(report_code: str, fight_id: int, player: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.FIGHT_COOLDOWNS,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        rows = result.fetchall()
        return [CooldownUsageResponse(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get cooldowns")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/consumables",
    response_model=list[ConsumablePlayerEntry],
)
async def get_fight_consumables(
    report_code: str, fight_id: int, player: str | None = None,
):
    session = await _get_session()
    try:
        result = await session.execute(
            q.CONSUMABLE_CHECK,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player}%" if player else None},
        )
        rows = result.fetchall()

        # Expected categories: flask OR elixir (mutually exclusive), food
        required_categories = {"flask", "food"}
        nice_to_have = {"weapon_oil"}

        # Group by player
        from collections import defaultdict
        players: dict[str, list] = defaultdict(list)
        for r in rows:
            players[r.player_name].append(r)

        entries = []
        for pname, consumables in sorted(players.items()):
            items = []
            found_categories = set()
            for c in consumables:
                items.append(ConsumableItem(
                    category=c.category,
                    ability_name=c.ability_name,
                    spell_id=c.spell_id,
                ))
                found_categories.add(c.category)

            has_flask_or_elixir = (
                "flask" in found_categories or "elixir" in found_categories
            )
            missing = []
            if not has_flask_or_elixir:
                missing.append("flask/elixir")
            for cat in sorted(required_categories - {"flask"}):
                if cat not in found_categories:
                    missing.append(cat)
            for cat in sorted(nice_to_have - found_categories):
                missing.append(cat)

            entries.append(ConsumablePlayerEntry(
                player_name=pname,
                consumables=items,
                missing=missing,
            ))
        return entries
    except Exception as e:
        logger.exception("Failed to get fight consumables")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/overheal/{player}",
    response_model=OverhealResponse,
)
async def fight_overheal(report_code: str, fight_id: int, player: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.OVERHEAL_ANALYSIS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player}%"},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No healing data for {player} in fight {fight_id}",
            )

        abilities = []
        total_effective = 0
        total_overheal = 0
        for r in rows:
            oh = r.overheal_total or 0
            total_effective += r.total
            total_overheal += oh
            abilities.append(OverhealAbility(
                ability_name=r.ability_name,
                spell_id=r.spell_id,
                total=r.total,
                overheal_total=oh,
                overheal_pct=float(r.overheal_pct) if r.overheal_pct else 0.0,
            ))

        grand_total = total_effective + total_overheal
        total_pct = (total_overheal / grand_total * 100) if grand_total > 0 else 0.0

        return OverhealResponse(
            player_name=player,
            total_effective=total_effective,
            total_overheal=total_overheal,
            total_overheal_pct=round(total_pct, 1),
            abilities=abilities,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get overheal data")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cancelled-casts/{player}",
    response_model=CancelledCastResponse | None,
)
async def fight_cancelled_casts(report_code: str, fight_id: int, player: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.CANCELLED_CASTS,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        row = result.fetchone()
        if not row:
            return None
        return CancelledCastResponse(**dict(row._mapping))
    except Exception as e:
        logger.exception("Failed to get cancelled casts")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()





@router.get(
    "/reports/{report_code}/wipe-progression/{encounter_name}",
    response_model=list[WipeProgressionAttempt],
)
async def wipe_progression(report_code: str, encounter_name: str):
    """Get attempt-by-attempt progression for an encounter in a report."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.WIPE_PROGRESSION,
            {"report_code": report_code, "encounter_name": f"%{encounter_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No attempts found for '{encounter_name}' in report {report_code}",
            )
        return [WipeProgressionAttempt(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get wipe progression")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats():
    session = await _get_session()
    try:
        result = await session.execute(q.DASHBOARD_STATS)
        row = result.fetchone()
        if not row:
            return DashboardStats(
                total_reports=0, total_kills=0, total_wipes=0,
                total_characters=0, total_encounters=0,
            )
        return DashboardStats(**dict(row._mapping))
    except Exception as e:
        logger.exception("Failed to get dashboard stats")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/dashboard/recent", response_model=list[RecentReportSummary])
async def dashboard_recent():
    session = await _get_session()
    try:
        result = await session.execute(q.RECENT_REPORTS)
        rows = result.fetchall()
        return [RecentReportSummary(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get recent reports")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/gear/{player_name}",
    response_model=list[GearSlotEntry],
)
async def get_gear_snapshot(report_code: str, fight_id: int, player_name: str):
    """Get gear snapshot for a player in a fight."""
    from shukketsu.pipeline.constants import GEAR_SLOTS

    session = await _get_session()
    try:
        result = await session.execute(
            q.GEAR_SNAPSHOT,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player_name}%"},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No gear data for {player_name} in fight {fight_id} "
                    f"of report {report_code}"
                ),
            )
        return [
            GearSlotEntry(
                slot=r.slot,
                slot_name=GEAR_SLOTS.get(r.slot, f"Slot {r.slot}"),
                item_id=r.item_id,
                item_level=r.item_level,
            )
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get gear snapshot")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/gear/compare", response_model=list[GearChangeEntry])
async def get_gear_comparison(player: str, old: str, new: str):
    """Compare gear between two reports."""
    from shukketsu.pipeline.constants import GEAR_SLOTS

    session = await _get_session()
    try:
        result = await session.execute(
            q.GEAR_CHANGES,
            {"player_name": f"%{player}%",
             "report_code_old": old,
             "report_code_new": new},
        )
        rows = result.fetchall()
        entries = []
        for r in rows:
            old_ilvl = r.old_ilvl
            new_ilvl = r.new_ilvl
            delta = None
            if old_ilvl is not None and new_ilvl is not None:
                delta = new_ilvl - old_ilvl
            entries.append(GearChangeEntry(
                slot=r.slot,
                slot_name=GEAR_SLOTS.get(r.slot, f"Slot {r.slot}"),
                old_item_id=r.old_item_id,
                old_ilvl=old_ilvl,
                new_item_id=r.new_item_id,
                new_ilvl=new_ilvl,
                ilvl_delta=delta,
            ))
        return entries
    except Exception as e:
        logger.exception("Failed to compare gear")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/regressions", response_model=list[RegressionEntry])
async def get_regressions_endpoint(player: str | None = None):
    """Get performance regressions/improvements for tracked characters."""
    session = await _get_session()
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
    except Exception as e:
        logger.exception("Failed to get regressions")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/phases",
    response_model=PhaseAnalysis,
)
async def fight_phases(report_code: str, fight_id: int):
    """Get phase breakdown for a specific fight."""
    from shukketsu.pipeline.constants import ENCOUNTER_PHASES, PhaseDef

    session = await _get_session()
    try:
        result = await session.execute(
            q.PHASE_BREAKDOWN,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": None},
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No data for fight {fight_id} in report {report_code}",
            )

        first = rows[0]
        encounter_name = first.encounter_name
        duration_ms = first.duration_ms

        # Look up phase definitions
        phases = ENCOUNTER_PHASES.get(encounter_name, [
            PhaseDef("Full Fight", 0.0, 1.0, "No phase data available"),
        ])

        phase_infos = []
        for phase in phases:
            est_start = int(duration_ms * phase.pct_start)
            est_end = int(duration_ms * phase.pct_end)
            phase_infos.append(PhaseInfo(
                name=phase.name,
                pct_start=phase.pct_start,
                pct_end=phase.pct_end,
                estimated_start_ms=est_start,
                estimated_end_ms=est_end,
                estimated_duration_ms=est_end - est_start,
                description=phase.description,
            ))

        players = []
        for r in rows:
            players.append(PhasePlayerPerformance(
                player_name=r.player_name,
                player_class=r.player_class,
                player_spec=r.player_spec,
                dps=r.dps,
                total_damage=r.total_damage,
                hps=r.hps,
                total_healing=r.total_healing,
                deaths=r.deaths,
                parse_percentile=r.parse_percentile,
            ))

        return PhaseAnalysis(
            report_code=report_code,
            fight_id=fight_id,
            encounter_name=encounter_name,
            duration_ms=duration_ms,
            kill=first.kill,
            phases=phase_infos,
            players=players,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get phase breakdown")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get("/reports/{report_code}/night-summary")
async def night_summary(
    report_code: str, output_format: str | None = None,
):
    """Generate a post-raid night summary for a report.

    When format=discord, returns a PlainTextResponse with Discord-ready
    markdown. Otherwise returns the JSON RaidNightSummary model.
    """
    from shukketsu.pipeline.summaries import build_raid_night_summary

    session = await _get_session()
    try:
        # Fetch fight-level aggregates
        fight_result = await session.execute(
            q.NIGHT_SUMMARY_FIGHTS, {"report_code": report_code},
        )
        fight_rows = fight_result.fetchall()
        if not fight_rows:
            raise HTTPException(
                status_code=404, detail=f"No data for report {report_code}",
            )

        # Fetch player-level details
        player_result = await session.execute(
            q.NIGHT_SUMMARY_PLAYERS, {"report_code": report_code},
        )
        player_rows = player_result.fetchall()

        # Fetch week-over-week comparison
        wow_data = None
        wow_result = await session.execute(
            q.WEEK_OVER_WEEK, {"report_code": report_code},
        )
        wow_row = wow_result.fetchone()
        if wow_row:
            wow_data = {
                "previous_report": wow_row.previous_report,
                "clear_time_delta_ms": wow_row.clear_time_delta_ms,
                "kills_delta": wow_row.kills_delta,
                "avg_parse_delta": (
                    float(wow_row.avg_parse_delta)
                    if wow_row.avg_parse_delta is not None else None
                ),
            }

        # Fetch player parse deltas for most improved / biggest regression
        player_deltas = None
        delta_result = await session.execute(
            q.PLAYER_PARSE_DELTAS, {"report_code": report_code},
        )
        delta_rows = delta_result.fetchall()
        if delta_rows:
            player_deltas = delta_rows

        summary = build_raid_night_summary(
            report_code, fight_rows, player_rows,
            wow_data=wow_data, player_deltas=player_deltas,
        )

        if output_format == "discord":
            from fastapi.responses import PlainTextResponse

            from shukketsu.pipeline.discord_format import (
                format_raid_summary_discord,
            )

            text = format_raid_summary_discord(summary)
            return PlainTextResponse(content=text)

        return RaidNightSummary(**summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate night summary for %s", report_code)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/events-available",
    response_model=EventsAvailable,
)
async def events_available(report_code: str):
    """Check if event-level data exists for a report."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.EVENT_DATA_EXISTS, {"report_code": report_code}
        )
        row = result.fetchone()
        return EventsAvailable(has_data=row.has_data if row else False)
    except Exception as e:
        logger.exception("Failed to check events availability")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cast-timeline/{player}",
    response_model=list[CastEventResponse],
)
async def fight_cast_timeline(
    report_code: str, fight_id: int, player: str,
):
    """Get cast event timeline for a player in a fight."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.CAST_TIMELINE,
            {
                "report_code": report_code,
                "fight_id": fight_id,
                "player_name": player,
            },
        )
        rows = result.fetchall()
        return [CastEventResponse(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get cast timeline")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/resources/{player}",
    response_model=list[ResourceSnapshotResponse],
)
async def fight_resources(
    report_code: str, fight_id: int, player: str,
):
    """Get resource snapshots for a player in a fight."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.RESOURCE_USAGE,
            {
                "report_code": report_code,
                "fight_id": fight_id,
                "player_name": player,
            },
        )
        rows = result.fetchall()
        return [
            ResourceSnapshotResponse(**dict(r._mapping)) for r in rows
        ]
    except Exception as e:
        logger.exception("Failed to get resource snapshots")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cooldown-windows/{player}",
    response_model=list[CooldownWindowResponse],
)
async def fight_cooldown_windows(
    report_code: str, fight_id: int, player: str,
):
    """Get cooldown usage windows with estimated DPS gain."""
    session = await _get_session()
    try:
        result = await session.execute(
            q.COOLDOWN_WINDOWS,
            {
                "report_code": report_code,
                "fight_id": fight_id,
                "player_name": player,
            },
        )
        rows = result.fetchall()
        entries = []
        for r in rows:
            cd_duration_ms = r.cooldown_sec * 1000
            window_start = r.first_use_ms or 0
            window_end = window_start + cd_duration_ms
            baseline_dps = r.baseline_dps or 0
            window_dps = baseline_dps * 1.2
            window_damage = int(window_dps * (cd_duration_ms / 1000))
            dps_gain = 20.0
            entries.append(CooldownWindowResponse(
                player_name=r.player_name,
                ability_name=r.ability_name,
                spell_id=r.spell_id,
                window_start_ms=window_start,
                window_end_ms=window_end,
                window_damage=window_damage,
                window_dps=round(window_dps, 1),
                baseline_dps=round(baseline_dps, 1),
                dps_gain_pct=dps_gain,
            ))
        return entries
    except Exception as e:
        logger.exception("Failed to get cooldown windows")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/dot-refreshes/{player}",
    response_model=list[DotRefreshResponse],
)
async def fight_dot_refreshes(report_code: str, fight_id: int, player: str):
    """Analyze DoT refresh patterns for a player in a fight."""
    from collections import defaultdict

    from shukketsu.pipeline.constants import CLASSIC_DOTS, DOT_BY_SPELL_ID

    session = await _get_session()
    try:
        # Get player class
        info_result = await session.execute(
            q.PLAYER_FIGHT_INFO,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        info_row = info_result.fetchone()
        if not info_row:
            raise HTTPException(
                status_code=404,
                detail=f"No data for {player} in fight {fight_id}",
            )

        player_class = info_row.player_class
        class_dots = CLASSIC_DOTS.get(player_class, [])
        dot_spell_ids = {d.spell_id for d in class_dots}

        if not dot_spell_ids:
            return []

        # Get cast events
        cast_result = await session.execute(
            q.CAST_EVENTS_FOR_DOT_ANALYSIS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        cast_rows = cast_result.fetchall()

        # Group by spell_id, filter to DoT spells only
        casts_by_spell: dict[int, list[int]] = defaultdict(list)
        spell_names: dict[int, str] = {}
        for r in cast_rows:
            if r.spell_id in dot_spell_ids:
                casts_by_spell[r.spell_id].append(r.timestamp_ms)
                spell_names[r.spell_id] = r.ability_name

        results = []
        for spell_id, timestamps in casts_by_spell.items():
            dot_def = DOT_BY_SPELL_ID.get(spell_id)
            if not dot_def or len(timestamps) < 2:
                continue

            total_refreshes = len(timestamps) - 1
            early_refreshes = 0
            remaining_values = []
            clipped_ticks_total = 0.0

            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i - 1]
                if gap < dot_def.duration_ms:
                    remaining_ms = dot_def.duration_ms - gap
                    remaining_values.append(remaining_ms)
                    # Early if > 30% of duration remains
                    if remaining_ms > 0.3 * dot_def.duration_ms:
                        early_refreshes += 1
                    clipped_ticks_total += (
                        remaining_ms / dot_def.tick_interval_ms
                    )

            avg_remaining = (
                sum(remaining_values) / len(remaining_values)
                if remaining_values else 0.0
            )
            early_pct = (
                (early_refreshes / total_refreshes * 100)
                if total_refreshes > 0 else 0.0
            )

            results.append(DotRefreshResponse(
                player_name=player,
                spell_id=spell_id,
                ability_name=spell_names.get(spell_id, dot_def.name),
                total_refreshes=total_refreshes,
                early_refreshes=early_refreshes,
                early_refresh_pct=round(early_pct, 1),
                avg_remaining_ms=round(avg_remaining, 1),
                clipped_ticks_est=round(clipped_ticks_total, 1),
            ))

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get DoT refresh analysis")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/rotation/{player}",
    response_model=RotationScoreResponse,
)
async def fight_rotation_score(
    report_code: str, fight_id: int, player: str,
):
    """Rule-based rotation scoring for a player in a fight."""
    import json

    session = await _get_session()
    try:
        # Get player info (class + spec)
        info_result = await session.execute(
            q.PLAYER_FIGHT_INFO,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        info_row = info_result.fetchone()
        if not info_row:
            raise HTTPException(
                status_code=404,
                detail=f"No data for {player} in fight {fight_id}",
            )

        spec = info_row.player_spec

        # Get cast metrics (GCD uptime, CPM)
        cm_result = await session.execute(
            q.FIGHT_CAST_METRICS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        cm_row = cm_result.fetchone()

        # Get cooldown usage
        cd_result = await session.execute(
            q.FIGHT_COOLDOWNS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        cd_rows = cd_result.fetchall()

        rules_checked = 0
        rules_passed = 0
        violations = []

        # Rule 1: GCD uptime > 85%
        if cm_row:
            rules_checked += 1
            if cm_row.gcd_uptime_pct >= 85.0:
                rules_passed += 1
            else:
                violations.append(
                    f"GCD uptime {cm_row.gcd_uptime_pct:.1f}% < 85%"
                )

            # Rule 2: CPM > 20
            rules_checked += 1
            if cm_row.casts_per_minute >= 20.0:
                rules_passed += 1
            else:
                violations.append(
                    f"CPM {cm_row.casts_per_minute:.1f} < 20"
                )

        # Rule 3: No cooldown efficiency below 60%
        for cd in cd_rows:
            rules_checked += 1
            if cd.efficiency_pct >= 60.0:
                rules_passed += 1
            else:
                violations.append(
                    f"{cd.ability_name} efficiency "
                    f"{cd.efficiency_pct:.1f}% < 60%"
                )

        score = (
            (rules_passed / rules_checked * 100)
            if rules_checked > 0 else 0.0
        )

        return RotationScoreResponse(
            player_name=player,
            spec=spec,
            score_pct=round(score, 1),
            rules_checked=rules_checked,
            rules_passed=rules_passed,
            violations_json=json.dumps(violations) if violations else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get rotation score")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/trinkets/{player}",
    response_model=list[TrinketProcResponse],
)
async def fight_trinket_procs(
    report_code: str, fight_id: int, player: str,
):
    """Track trinket proc uptimes for a player in a fight."""
    from shukketsu.pipeline.constants import CLASSIC_TRINKETS

    session = await _get_session()
    try:
        result = await session.execute(
            q.PLAYER_BUFFS_FOR_TRINKETS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        rows = result.fetchall()

        entries = []
        for r in rows:
            trinket_def = CLASSIC_TRINKETS.get(r.spell_id)
            if not trinket_def:
                continue

            actual = float(r.uptime_pct)
            expected = trinket_def.expected_uptime_pct

            if actual >= expected:
                grade = "EXCELLENT"
            elif actual >= expected * 0.8:
                grade = "GOOD"
            else:
                grade = "POOR"

            entries.append(TrinketProcResponse(
                player_name=player,
                trinket_name=trinket_def.name,
                spell_id=r.spell_id,
                uptime_pct=round(actual, 1),
                expected_uptime_pct=expected,
                grade=grade,
            ))

        return entries
    except Exception as e:
        logger.exception("Failed to get trinket procs")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/phases/{player}",
    response_model=list[PhaseMetricResponse],
)
async def fight_phases_player(
    report_code: str, fight_id: int, player: str,
):
    """Get per-player phase metrics for a fight."""
    from shukketsu.pipeline.constants import ENCOUNTER_PHASES, PhaseDef

    session = await _get_session()
    try:
        # Get fight info (encounter name, duration, DPS)
        info_result = await session.execute(
            q.PLAYER_FIGHT_INFO,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        info_row = info_result.fetchone()
        if not info_row:
            raise HTTPException(
                status_code=404,
                detail=f"No data for {player} in fight {fight_id}",
            )

        duration_ms = info_row.fight_duration_ms
        overall_dps = info_row.dps

        # Look up encounter name from encounters table via encounter_id
        from sqlalchemy import text as sa_text
        enc_result = await session.execute(
            sa_text("SELECT name FROM encounters WHERE id = :enc_id"),
            {"enc_id": info_row.encounter_id},
        )
        enc_row = enc_result.fetchone()
        encounter_name = enc_row.name if enc_row else "Unknown"

        phases = ENCOUNTER_PHASES.get(encounter_name, [
            PhaseDef("Full Fight", 0.0, 1.0, "No phase data available"),
        ])

        # Get cast events for the player in this fight
        cast_result = await session.execute(
            q.CAST_EVENTS_FOR_PHASES,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        cast_rows = cast_result.fetchall()
        cast_timestamps = [r.timestamp_ms for r in cast_rows]
        total_casts = len(cast_timestamps)

        # Compute the fight's absolute start time for phase boundaries
        # Phase boundaries are relative to fight start (timestamp 0)
        # cast_events timestamps are absolute; assume min timestamp ~ fight
        # start. We work with offsets: phase_start = pct_start * duration_ms
        fight_start = min(cast_timestamps) if cast_timestamps else 0

        results = []
        for phase in phases:
            phase_start_ms = int(duration_ms * phase.pct_start)
            phase_end_ms = int(duration_ms * phase.pct_end)
            phase_duration_ms = phase_end_ms - phase_start_ms

            # Count casts that fall within this phase (offset from fight
            # start)
            phase_casts = 0
            for ts in cast_timestamps:
                offset = ts - fight_start
                if phase_start_ms <= offset < phase_end_ms:
                    phase_casts += 1

            # Estimate phase DPS proportionally from overall DPS
            phase_dps = None
            if total_casts > 0 and overall_dps:
                phase_dps = round(
                    overall_dps * (phase_casts / total_casts), 1,
                )

            # Estimate GCD uptime: assume ~1.5s GCD per cast
            gcd_uptime_pct = None
            if phase_duration_ms > 0:
                gcd_time = phase_casts * 1500  # 1.5s GCD
                gcd_uptime_pct = round(
                    min(gcd_time / phase_duration_ms * 100, 100.0), 1,
                )

            is_downtime = phase_casts == 0 and phase_duration_ms > 0

            results.append(PhaseMetricResponse(
                player_name=player,
                phase_name=phase.name,
                phase_start_ms=phase_start_ms,
                phase_end_ms=phase_end_ms,
                is_downtime=is_downtime,
                phase_dps=phase_dps,
                phase_casts=phase_casts,
                phase_gcd_uptime_pct=gcd_uptime_pct,
            ))

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get player phase metrics")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()
