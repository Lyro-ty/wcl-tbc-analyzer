"""Report CRUD, ingest, and dashboard endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import cooldown, get_db
from shukketsu.api.models import (
    AbilitiesAvailable,
    DashboardStats,
    EventDataResponse,
    EventsAvailable,
    ExecutionBoss,
    IngestRequest,
    IngestResponse,
    RaidSummaryFight,
    RecentReportSummary,
    ReportSummary,
    SpeedComparison,
    TableDataResponse,
    WipeProgressionAttempt,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/reports", response_model=list[ReportSummary])
async def list_reports(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(q.REPORTS_LIST)
        rows = result.fetchall()
        return [ReportSummary(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to list reports")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/reports/{report_code}/summary", response_model=list[RaidSummaryFight])
async def report_summary(
    report_code: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(q.RAID_SUMMARY, {"report_code": report_code})
        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No data for report {report_code}")
        return [RaidSummaryFight(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get report summary")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/reports/{report_code}/execution", response_model=list[ExecutionBoss])
async def report_execution(
    report_code: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.RAID_EXECUTION_SUMMARY, {"report_code": report_code}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"No kill data for report {report_code}"
            )
        return [ExecutionBoss(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get execution data")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/reports/{report_code}/speed", response_model=list[SpeedComparison])
async def report_speed(
    report_code: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.RAID_VS_TOP_SPEED, {"report_code": report_code}
        )
        rows = result.fetchall()
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"No kill data for report {report_code}"
            )
        return [SpeedComparison(**dict(r._mapping)) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get speed data")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/abilities-available",
    response_model=AbilitiesAvailable,
)
async def abilities_available(
    report_code: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.TABLE_DATA_EXISTS, {"report_code": report_code}
        )
        row = result.fetchone()
        return AbilitiesAvailable(has_data=row.has_data if row else False)
    except Exception:
        logger.exception("Failed to check abilities availability")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/events-available",
    response_model=EventsAvailable,
)
async def events_available(
    report_code: str, session: AsyncSession = Depends(get_db),
):
    """Check if event-level data exists for a report."""
    try:
        result = await session.execute(
            q.EVENT_DATA_EXISTS, {"report_code": report_code}
        )
        row = result.fetchone()
        return EventsAvailable(has_data=row.has_data if row else False)
    except Exception:
        logger.exception("Failed to check events availability")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post(
    "/ingest",
    response_model=IngestResponse,
    dependencies=[cooldown("ingest", 120)],
)
async def ingest_report_endpoint(
    req: IngestRequest, session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        await session.rollback()
        logger.exception("Failed to ingest report %s", req.report_code)
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post(
    "/reports/{report_code}/table-data",
    response_model=TableDataResponse,
    dependencies=[cooldown("table_data", 60)],
)
async def fetch_table_data(
    report_code: str, session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        await session.rollback()
        logger.exception("Failed to fetch table data for %s", report_code)
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post(
    "/reports/{report_code}/event-data",
    response_model=EventDataResponse,
    dependencies=[cooldown("event_data", 60)],
)
async def fetch_event_data(
    report_code: str, session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        await session.rollback()
        logger.exception("Failed to fetch event data for %s", report_code)
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/wipe-progression/{encounter_name}",
    response_model=list[WipeProgressionAttempt],
)
async def wipe_progression(
    report_code: str, encounter_name: str,
    session: AsyncSession = Depends(get_db),
):
    """Get attempt-by-attempt progression for an encounter in a report."""
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
    except Exception:
        logger.exception("Failed to get wipe progression")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(q.DASHBOARD_STATS)
        row = result.fetchone()
        if not row:
            return DashboardStats(
                total_reports=0, total_kills=0, total_wipes=0,
                total_characters=0, total_encounters=0,
            )
        return DashboardStats(**dict(row._mapping))
    except Exception:
        logger.exception("Failed to get dashboard stats")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/dashboard/recent", response_model=list[RecentReportSummary])
async def dashboard_recent(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(q.RECENT_REPORTS)
        rows = result.fetchall()
        return [RecentReportSummary(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to get recent reports")
        raise HTTPException(status_code=500, detail="Internal server error") from None
