"""REST data endpoints for structured dashboard views."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.models import (
    AbilitiesAvailable,
    AbilityMetricResponse,
    BuffUptimeResponse,
    CancelledCastResponse,
    CastMetricResponse,
    CharacterFightSummary,
    CharacterInfo,
    CharacterProfile,
    CharacterRecentParse,
    CharacterReportSummary,
    ConsumableItem,
    ConsumablePlayerEntry,
    CooldownUsageResponse,
    DashboardStats,
    DeathDetailResponse,
    DeathEntry,
    EncounterInfo,
    EventDataResponse,
    EventsAvailableResponse,
    ExecutionBoss,
    FightPlayer,
    GearChangeEntry,
    GearSlotEntry,
    IngestRequest,
    IngestResponse,
    OverhealAbility,
    OverhealResponse,
    PersonalBestEntry,
    ProgressionPoint,
    RaidComparison,
    RaidNightSummary,
    RaidSummaryFight,
    RankingsRefreshResponse,
    RecentReportSummary,
    RegisterCharacterRequest,
    RegressionEntry,
    ReportSummary,
    SpecLeaderboardEntry,
    SpeedComparison,
    TableDataResponse,
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
    "/reports/{report_code}/events-available",
    response_model=EventsAvailableResponse,
)
async def events_available(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(
            q.EVENT_DATA_EXISTS, {"report_code": report_code}
        )
        row = result.fetchone()
        return EventsAvailableResponse(has_data=row.has_data if row else False)
    except Exception as e:
        logger.exception("Failed to check events availability")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()


@router.post(
    "/reports/{report_code}/event-data",
    response_model=EventDataResponse,
)
async def fetch_event_data(report_code: str):
    from shukketsu.config import get_settings
    from shukketsu.pipeline.event_data import ingest_event_data_for_report
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
            rows = await ingest_event_data_for_report(wcl, session, report_code)
        await session.commit()
        logger.info("Fetched event data for %s: %d rows", report_code, rows)
        return EventDataResponse(report_code=report_code, event_rows=rows)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to fetch event data for %s", report_code)
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


@router.get("/reports/{report_code}/night-summary")
async def night_summary(
    report_code: str, format: str | None = None,
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

        if format == "discord":
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
