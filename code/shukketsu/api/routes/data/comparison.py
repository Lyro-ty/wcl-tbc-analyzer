"""Raid comparison and gear comparison endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import get_db
from shukketsu.api.models import (
    GearChangeEntry,
    RaidComparison,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/compare", response_model=list[RaidComparison])
async def compare_raids(
    a: str, b: str, session: AsyncSession = Depends(get_db),
):
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


@router.get("/gear/compare", response_model=list[GearChangeEntry])
async def get_gear_comparison(
    player: str, old: str, new: str,
    session: AsyncSession = Depends(get_db),
):
    """Compare gear between two reports."""
    from shukketsu.pipeline.constants import GEAR_SLOTS

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
