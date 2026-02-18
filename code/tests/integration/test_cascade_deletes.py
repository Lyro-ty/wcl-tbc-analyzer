"""Test CASCADE DELETE behavior with real PostgreSQL."""

import pytest
from sqlalchemy import text

from shukketsu.db.models import Encounter, Fight, FightPerformance, Report


@pytest.mark.integration
async def test_delete_report_cascades_to_fights(session):
    """Deleting a report cascades to its fights."""
    # Insert encounter (needed for FK)
    session.add(Encounter(id=99999, name="Test Boss", zone_id=1, zone_name="Test Zone"))
    await session.flush()

    # Insert report
    session.add(Report(code="test1", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    # Insert fight
    session.add(Fight(
        report_code="test1", fight_id=1, encounter_id=99999,
        start_time=1000, end_time=1500, kill=True,
    ))
    await session.flush()

    # Delete report — should cascade to fights
    await session.execute(text("DELETE FROM reports WHERE code = 'test1'"))
    await session.flush()

    result = await session.execute(
        text("SELECT COUNT(*) FROM fights WHERE report_code = 'test1'")
    )
    assert result.scalar() == 0


@pytest.mark.integration
async def test_delete_fight_cascades_to_performances(session):
    """Deleting a fight cascades to its performances."""
    session.add(Encounter(id=99998, name="Test Boss 2", zone_id=1, zone_name="Test Zone"))
    session.add(Report(code="test2", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="test2", fight_id=1, encounter_id=99998,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    session.add(FightPerformance(
        fight_id=fight.id, player_name="TestPlayer", player_class="Warrior",
        player_spec="Arms", player_server="Test",
    ))
    await session.flush()

    # Delete fight — should cascade to performances
    await session.execute(text(f"DELETE FROM fights WHERE id = {fight.id}"))
    await session.flush()

    result = await session.execute(
        text(f"SELECT COUNT(*) FROM fight_performances WHERE fight_id = {fight.id}")
    )
    assert result.scalar() == 0


@pytest.mark.integration
async def test_delete_report_cascades_through_fights_to_performances(session):
    """Deleting a report cascades through fights to performances."""
    session.add(Encounter(id=99997, name="Test Boss 3", zone_id=1, zone_name="Test Zone"))
    session.add(Report(code="test3", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    fight = Fight(
        report_code="test3", fight_id=1, encounter_id=99997,
        start_time=1000, end_time=1500, kill=True,
    )
    session.add(fight)
    await session.flush()

    session.add(FightPerformance(
        fight_id=fight.id, player_name="TestPlayer", player_class="Warrior",
        player_spec="Arms", player_server="Test",
    ))
    await session.flush()

    fight_id = fight.id

    # Delete report — should cascade through fights to performances
    await session.execute(text("DELETE FROM reports WHERE code = 'test3'"))
    await session.flush()

    result = await session.execute(
        text(f"SELECT COUNT(*) FROM fight_performances WHERE fight_id = {fight_id}")
    )
    assert result.scalar() == 0


@pytest.mark.integration
async def test_delete_encounter_cascades_to_fights(session):
    """Deleting an encounter cascades to its fights."""
    session.add(Encounter(id=99996, name="Test Boss 4", zone_id=1, zone_name="Test Zone"))
    session.add(Report(code="test4", title="Test", start_time=1000, end_time=2000))
    await session.flush()

    session.add(Fight(
        report_code="test4", fight_id=1, encounter_id=99996,
        start_time=1000, end_time=1500, kill=True,
    ))
    await session.flush()

    # Delete encounter — should cascade to fights
    await session.execute(text("DELETE FROM encounters WHERE id = 99996"))
    await session.flush()

    result = await session.execute(
        text("SELECT COUNT(*) FROM fights WHERE encounter_id = 99996")
    )
    assert result.scalar() == 0
