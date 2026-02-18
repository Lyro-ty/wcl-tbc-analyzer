"""Test CHECK constraints with real PostgreSQL."""

import pytest
from sqlalchemy.exc import IntegrityError

from shukketsu.db.models import (
    BuffUptime,
    CancelledCast,
    CastMetric,
    CooldownUsage,
    Encounter,
    Fight,
    FightPerformance,
    Report,
    ResourceSnapshot,
)


@pytest.mark.integration
async def test_parse_percentile_rejects_over_100(session):
    """CHECK constraint rejects parse_percentile > 100."""
    session.add(Encounter(id=99990, name="CK Boss", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest1", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest1", fight_id=1, encounter_id=99990,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(FightPerformance(
            fight_id=fight.id, player_name="Bad", player_class="Warrior",
            player_spec="Arms", player_server="Test",
            parse_percentile=150.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_parse_percentile_rejects_negative(session):
    """CHECK constraint rejects parse_percentile < 0."""
    session.add(Encounter(id=99991, name="CK Boss Neg", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest1n", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest1n", fight_id=1, encounter_id=99991,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(FightPerformance(
            fight_id=fight.id, player_name="Bad", player_class="Warrior",
            player_spec="Arms", player_server="Test",
            parse_percentile=-10.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_dps_rejects_negative(session):
    """CHECK constraint rejects negative DPS."""
    session.add(Encounter(id=99989, name="CK Boss 2", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest2", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest2", fight_id=1, encounter_id=99989,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(FightPerformance(
            fight_id=fight.id, player_name="Bad", player_class="Warrior",
            player_spec="Arms", player_server="Test",
            dps=-100.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_valid_data_accepted(session):
    """Valid data passes all constraints."""
    session.add(Encounter(id=99988, name="CK Boss 3", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest3", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest3", fight_id=1, encounter_id=99988,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    session.add(FightPerformance(
        fight_id=fight.id, player_name="Good", player_class="Warrior",
        player_spec="Arms", player_server="Test",
        dps=1500.0, parse_percentile=95.0,
    ))
    await session.flush()  # Should succeed


@pytest.mark.integration
async def test_buff_uptime_rejects_over_100(session):
    """CHECK constraint rejects buff uptime_pct > 100."""
    session.add(Encounter(id=99987, name="CK Boss 4", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest4", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest4", fight_id=1, encounter_id=99987,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(BuffUptime(
            fight_id=fight.id, player_name="Bad", metric_type="buff",
            ability_name="Test Buff", spell_id=1,
            uptime_pct=110.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_gcd_uptime_rejects_over_100(session):
    """CHECK constraint rejects gcd_uptime_pct > 100."""
    session.add(Encounter(id=99986, name="CK Boss 5", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest5", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest5", fight_id=1, encounter_id=99986,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(CastMetric(
            fight_id=fight.id, player_name="Bad",
            total_casts=10, casts_per_minute=5.0,
            gcd_uptime_pct=105.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_cooldown_efficiency_rejects_over_100(session):
    """CHECK constraint rejects efficiency_pct > 100."""
    session.add(Encounter(id=99985, name="CK Boss 6", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest6", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest6", fight_id=1, encounter_id=99985,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(CooldownUsage(
            fight_id=fight.id, player_name="Bad",
            spell_id=1, ability_name="Test CD", cooldown_sec=60,
            times_used=5, max_possible_uses=3,
            efficiency_pct=150.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_cancel_pct_rejects_negative(session):
    """CHECK constraint rejects cancel_pct < 0."""
    session.add(Encounter(id=99984, name="CK Boss 7", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest7", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest7", fight_id=1, encounter_id=99984,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(CancelledCast(
            fight_id=fight.id, player_name="Bad",
            total_begins=10, total_completions=8,
            cancel_count=2, cancel_pct=-5.0,  # Invalid!
        ))
        await session.flush()


@pytest.mark.integration
async def test_resource_time_at_zero_pct_rejects_over_100(session):
    """CHECK constraint rejects time_at_zero_pct > 100."""
    session.add(Encounter(id=99983, name="CK Boss 8", zone_id=1, zone_name="Test"))
    session.add(Report(code="cktest8", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="cktest8", fight_id=1, encounter_id=99983,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    with pytest.raises(IntegrityError):
        session.add(ResourceSnapshot(
            fight_id=fight.id, player_name="Bad",
            resource_type="mana", min_value=0, max_value=10000,
            avg_value=5000.0, time_at_zero_ms=0,
            time_at_zero_pct=120.0,  # Invalid!
        ))
        await session.flush()
