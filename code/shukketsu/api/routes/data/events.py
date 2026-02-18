"""Event-data endpoints: cast timeline, cooldowns, resources, DoT, rotation, trinkets."""

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import get_db
from shukketsu.api.models import (
    CancelledCastResponse,
    CastEventResponse,
    CastMetricResponse,
    CooldownUsageResponse,
    CooldownWindowResponse,
    DotRefreshResponse,
    PhaseMetricResponse,
    ResourceSnapshotResponse,
    RotationScoreResponse,
    TrinketProcResponse,
)
from shukketsu.db import queries as q

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cast-metrics/{player}",
    response_model=CastMetricResponse | None,
)
async def fight_cast_metrics(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.FIGHT_CAST_METRICS,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        row = result.fetchone()
        if not row:
            return None
        return CastMetricResponse(**dict(row._mapping))
    except Exception:
        logger.exception("Failed to get cast metrics")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cooldowns/{player}",
    response_model=list[CooldownUsageResponse],
)
async def fight_cooldowns(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.FIGHT_COOLDOWNS,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        rows = result.fetchall()
        return [CooldownUsageResponse(**dict(r._mapping)) for r in rows]
    except Exception:
        logger.exception("Failed to get cooldowns")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cancelled-casts/{player}",
    response_model=CancelledCastResponse | None,
)
async def fight_cancelled_casts(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            q.CANCELLED_CASTS,
            {"report_code": report_code, "fight_id": fight_id, "player_name": player},
        )
        row = result.fetchone()
        if not row:
            return None
        return CancelledCastResponse(**dict(row._mapping))
    except Exception:
        logger.exception("Failed to get cancelled casts")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cast-timeline/{player}",
    response_model=list[CastEventResponse],
)
async def fight_cast_timeline(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Get cast event timeline for a player in a fight."""
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
    except Exception:
        logger.exception("Failed to get cast timeline")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/resources/{player}",
    response_model=list[ResourceSnapshotResponse],
)
async def fight_resources(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Get resource snapshots for a player in a fight."""
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
    except Exception:
        logger.exception("Failed to get resource snapshots")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/cooldown-windows/{player}",
    response_model=list[CooldownWindowResponse],
)
async def fight_cooldown_windows(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Get cooldown usage windows with estimated DPS gain."""
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
    except Exception:
        logger.exception("Failed to get cooldown windows")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/dot-refreshes/{player}",
    response_model=list[DotRefreshResponse],
)
async def fight_dot_refreshes(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Analyze DoT refresh patterns for a player in a fight."""
    from shukketsu.pipeline.constants import CLASSIC_DOTS, DOT_BY_SPELL_ID

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
    except Exception:
        logger.exception("Failed to get DoT refresh analysis")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/rotation/{player}",
    response_model=RotationScoreResponse,
)
async def fight_rotation_score(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Rule-based rotation scoring for a player in a fight."""
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
    except Exception:
        logger.exception("Failed to get rotation score")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/trinkets/{player}",
    response_model=list[TrinketProcResponse],
)
async def fight_trinket_procs(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Track trinket proc uptimes for a player in a fight."""
    from shukketsu.pipeline.constants import CLASSIC_TRINKETS

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
    except Exception:
        logger.exception("Failed to get trinket procs")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/reports/{report_code}/fights/{fight_id}/phases/{player}",
    response_model=list[PhaseMetricResponse],
)
async def fight_phases_player(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Get per-player phase metrics for a fight."""
    from shukketsu.pipeline.constants import ENCOUNTER_PHASES, PhaseDef

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
    except Exception:
        logger.exception("Failed to get player phase metrics")
        raise HTTPException(status_code=500, detail="Internal server error") from None
