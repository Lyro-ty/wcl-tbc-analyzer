"""Benchmark and watched guild API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import cooldown, get_db
from shukketsu.db import queries as q
from shukketsu.db.models import WatchedGuild

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class BenchmarkSummary(BaseModel):
    encounter_id: int
    encounter_name: str
    sample_size: int
    computed_at: datetime


class BenchmarkDetail(BaseModel):
    encounter_id: int
    encounter_name: str
    sample_size: int
    computed_at: datetime
    benchmarks: dict


class WatchedGuildResponse(BaseModel):
    id: int
    guild_name: str
    wcl_guild_id: int
    server_slug: str
    server_region: str
    is_active: bool


class AddWatchedGuildRequest(BaseModel):
    guild_name: str
    wcl_guild_id: int
    server_slug: str
    server_region: str = "US"


class BenchmarkRefreshResponse(BaseModel):
    discovered: int
    ingested: int
    computed: int
    errors: list[str]


# ---------------------------------------------------------------------------
# Benchmark endpoints
# ---------------------------------------------------------------------------

@router.get("/benchmarks", response_model=list[BenchmarkSummary])
async def list_benchmarks(session: AsyncSession = Depends(get_db)):
    """List all encounter benchmarks (summary)."""
    from sqlalchemy import text

    try:
        result = await session.execute(text(
            "SELECT eb.encounter_id, e.name AS encounter_name,"
            " eb.sample_size, eb.computed_at"
            " FROM encounter_benchmarks eb"
            " JOIN encounters e ON e.id = eb.encounter_id"
            " ORDER BY e.name"
        ))
        rows = result.fetchall()
        return [BenchmarkSummary(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to list benchmarks")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None


@router.get("/benchmarks/{encounter}", response_model=BenchmarkDetail)
async def get_benchmark(
    encounter: str, session: AsyncSession = Depends(get_db),
):
    """Full benchmark for an encounter."""
    try:
        result = await session.execute(
            q.GET_ENCOUNTER_BENCHMARK,
            {"encounter_name": f"%{encounter}%"},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No benchmark data for '{encounter}'",
            )
        return BenchmarkDetail(**dict(row._mapping))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get benchmark")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None


@router.get(
    "/benchmarks/{encounter}/{class_name}/{spec_name}",
    response_model=dict,
)
async def get_spec_benchmark(
    encounter: str, class_name: str, spec_name: str,
    session: AsyncSession = Depends(get_db),
):
    """Spec-specific benchmark for an encounter."""
    try:
        result = await session.execute(
            q.GET_ENCOUNTER_BENCHMARK,
            {"encounter_name": f"%{encounter}%"},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No benchmark data for '{encounter}'",
            )

        benchmarks = row._mapping["benchmarks"]
        by_spec = benchmarks.get("by_spec", {})
        spec_key = f"{spec_name} {class_name}"
        if spec_key not in by_spec:
            raise HTTPException(
                status_code=404,
                detail=f"No benchmark data for {spec_name} {class_name}"
                f" on '{encounter}'",
            )
        return by_spec[spec_key]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get spec benchmark")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None


@router.post(
    "/benchmarks/refresh",
    response_model=BenchmarkRefreshResponse,
    dependencies=[cooldown("benchmark_refresh", 3600)],
)
async def refresh_benchmarks(
    zone_id: int | None = None,
    force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """Trigger benchmark pipeline (1hr cooldown)."""
    from sqlalchemy import select as sa_select

    from shukketsu.api.deps import get_wcl_factory
    from shukketsu.db.models import Encounter
    from shukketsu.pipeline.benchmarks import run_benchmark_pipeline

    try:
        stmt = sa_select(Encounter.id)
        if zone_id is not None:
            stmt = stmt.where(Encounter.zone_id == zone_id)
        rows = await session.execute(stmt)
        encounter_ids = [r[0] for r in rows]
        if not encounter_ids:
            raise HTTPException(
                status_code=404, detail="No encounters found"
            )

        async with get_wcl_factory()() as wcl:
            result = await run_benchmark_pipeline(
                wcl, session, force=force,
            )
        logger.info(
            "Benchmark refresh: %d discovered, %d ingested, "
            "%d computed, %d errors",
            result.discovered, result.ingested,
            result.computed, len(result.errors),
        )
        return BenchmarkRefreshResponse(
            discovered=result.discovered,
            ingested=result.ingested,
            computed=result.computed,
            errors=result.errors,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to refresh benchmarks")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None


# ---------------------------------------------------------------------------
# Watched guild endpoints
# ---------------------------------------------------------------------------

@router.get("/watched-guilds", response_model=list[WatchedGuildResponse])
async def list_watched_guilds(session: AsyncSession = Depends(get_db)):
    """List all watched guilds."""
    try:
        result = await session.execute(
            select(WatchedGuild).order_by(WatchedGuild.guild_name)
        )
        guilds = result.scalars().all()
        return [
            WatchedGuildResponse(
                id=g.id,
                guild_name=g.guild_name,
                wcl_guild_id=g.wcl_guild_id,
                server_slug=g.server_slug,
                server_region=g.server_region,
                is_active=g.is_active,
            )
            for g in guilds
        ]
    except Exception:
        logger.exception("Failed to list watched guilds")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None


@router.post(
    "/watched-guilds",
    response_model=WatchedGuildResponse,
    status_code=201,
)
async def add_watched_guild(
    body: AddWatchedGuildRequest,
    session: AsyncSession = Depends(get_db),
):
    """Add a watched guild."""
    try:
        guild = WatchedGuild(
            guild_name=body.guild_name,
            wcl_guild_id=body.wcl_guild_id,
            server_slug=body.server_slug,
            server_region=body.server_region,
        )
        session.add(guild)
        await session.commit()
        await session.refresh(guild)
        return WatchedGuildResponse(
            id=guild.id,
            guild_name=guild.guild_name,
            wcl_guild_id=guild.wcl_guild_id,
            server_slug=guild.server_slug,
            server_region=guild.server_region,
            is_active=guild.is_active,
        )
    except Exception:
        logger.exception("Failed to add watched guild")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None


@router.delete("/watched-guilds/{guild_id}", status_code=204)
async def remove_watched_guild(
    guild_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Remove a watched guild."""
    try:
        result = await session.get(WatchedGuild, guild_id)
        if not result:
            raise HTTPException(
                status_code=404, detail=f"Watched guild {guild_id} not found"
            )
        await session.delete(result)
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to remove watched guild")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None
