"""Fight details, deaths, abilities, buffs, consumables, overheal, gear, phases."""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import get_db
from shukketsu.api.models import (
    AbilityMetricResponse,
    BuffUptimeResponse,
    ConsumableItem,
    ConsumablePlayerEntry,
    DeathDetailResponse,
    DeathEntry,
    FightPlayer,
    GearSlotEntry,
    OverhealAbility,
    OverhealResponse,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/reports/{report_code}/fights/{fight_id}",
    response_model=list[FightPlayer],
)
async def fight_details(
    report_code: str, fight_id: int,
    session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        logger.exception("Failed to get fight details")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/reports/{report_code}/deaths", response_model=list[DeathEntry])
async def report_deaths(
    report_code: str, session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(q.REPORT_DEATHS, {"report_code": report_code})
        rows = result.fetchall()
        return [DeathEntry(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to get death data")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/deaths",
    response_model=list[DeathDetailResponse],
)
async def fight_deaths(
    report_code: str, fight_id: int,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.FIGHT_DEATHS, {"report_code": report_code, "fight_id": fight_id}
        )
        rows = result.fetchall()
        return [DeathDetailResponse(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to get fight deaths")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/abilities",
    response_model=list[AbilityMetricResponse],
)
async def fight_abilities(
    report_code: str, fight_id: int,
    session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        logger.exception("Failed to get fight abilities")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/abilities/{player}",
    response_model=list[AbilityMetricResponse],
)
async def player_abilities(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        logger.exception("Failed to get player abilities")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/buffs",
    response_model=list[BuffUptimeResponse],
)
async def fight_buffs(
    report_code: str, fight_id: int,
    session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        logger.exception("Failed to get fight buffs")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/buffs/{player}",
    response_model=list[BuffUptimeResponse],
)
async def player_buffs(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        logger.exception("Failed to get player buffs")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/consumables",
    response_model=list[ConsumablePlayerEntry],
)
async def get_fight_consumables(
    report_code: str, fight_id: int, player: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.CONSUMABLE_CHECK,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": f"%{player}%" if player else None},
        )
        rows = result.fetchall()

        # Expected categories: flask OR elixir (mutually exclusive), food
        required_categories = {"flask", "food"}
        weapon_enhancements = {"weapon_oil", "weapon_stone"}

        # Group by player
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
                "flask" in found_categories
                or "battle_elixir" in found_categories
                or "guardian_elixir" in found_categories
            )
            missing = []
            if not has_flask_or_elixir:
                missing.append("flask/elixir")
            for cat in sorted(required_categories - {"flask"}):
                if cat not in found_categories:
                    missing.append(cat)
            if not (found_categories & weapon_enhancements):
                missing.append("weapon oil/stone")

            entries.append(ConsumablePlayerEntry(
                player_name=pname,
                consumables=items,
                missing=missing,
            ))
        return entries
    except Exception:
        logger.exception("Failed to get fight consumables")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/overheal/{player}",
    response_model=OverhealResponse,
)
async def fight_overheal(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
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
    except Exception:
        logger.exception("Failed to get overheal data")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/gear/{player_name}",
    response_model=list[GearSlotEntry],
)
async def get_gear_snapshot(
    report_code: str, fight_id: int, player_name: str,
    session: AsyncSession = Depends(get_db),
):
    """Get gear snapshot for a player in a fight."""
    from shukketsu.pipeline.constants import GEAR_SLOTS

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
    except Exception:
        logger.exception("Failed to get gear snapshot")
        raise HTTPException(status_code=500, detail="Internal server error") from None
