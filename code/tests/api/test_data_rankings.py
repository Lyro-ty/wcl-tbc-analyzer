"""Tests for encounters, leaderboard, and comparison endpoints."""

from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import make_row

# ---------------------------------------------------------------------------
# GET /api/data/encounters
# ---------------------------------------------------------------------------

async def test_list_encounters_ok(client, mock_session):
    """Returns list of encounter definitions."""
    mock_row = make_row(
        id=201101, name="Patchwerk", zone_id=2017,
        zone_name="Naxxramas", fight_count=50,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/encounters")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Patchwerk"
    assert data[0]["zone_id"] == 2017


async def test_list_encounters_empty(client, mock_session):
    """Returns empty list when no encounters seeded."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/encounters")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/leaderboard/{encounter}
# ---------------------------------------------------------------------------

async def test_spec_leaderboard_ok(client, mock_session):
    """Returns spec leaderboard for an encounter."""
    mock_row = make_row(
        player_class="Warrior", player_spec="Arms",
        sample_size=50, avg_dps=2200.0, max_dps=3100.0,
        median_dps=2100.0, avg_parse=85.0, avg_ilvl=130.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/leaderboard/Patchwerk")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["player_class"] == "Warrior"
    assert data[0]["max_dps"] == 3100.0


async def test_spec_leaderboard_404(client, mock_session):
    """Returns 404 when no leaderboard data for encounter."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/leaderboard/FakeBoss")
    assert resp.status_code == 404


async def test_spec_leaderboard_multiple_specs(client, mock_session):
    """Returns entries for multiple specs."""
    rows = [
        make_row(
            player_class=cls, player_spec=spec,
            sample_size=30, avg_dps=dps, max_dps=dps + 500,
            median_dps=dps - 100, avg_parse=80.0, avg_ilvl=130.0,
        )
        for cls, spec, dps in [
            ("Warrior", "Arms", 2200.0),
            ("Rogue", "Combat", 2100.0),
            ("Hunter", "Beast Mastery", 1900.0),
        ]
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/leaderboard/Patchwerk")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


# ---------------------------------------------------------------------------
# GET /api/data/compare
# ---------------------------------------------------------------------------

async def test_compare_raids_ok(client, mock_session):
    """Returns side-by-side raid comparison."""
    mock_row = make_row(
        encounter_name="Patchwerk",
        a_duration_ms=120000, b_duration_ms=130000,
        a_deaths=2, b_deaths=5,
        a_interrupts=10, b_interrupts=8,
        a_dispels=3, b_dispels=4,
        a_avg_dps=2200.0, b_avg_dps=2000.0,
        a_players=25, b_players=25,
        a_comp="5 tanks, 8 healers, 12 DPS",
        b_comp="4 tanks, 9 healers, 12 DPS",
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/compare?a=rpt1&b=rpt2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["a_duration_ms"] == 120000
    assert data[0]["b_duration_ms"] == 130000


async def test_compare_raids_404(client, mock_session):
    """Returns 404 when no overlapping kills."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/compare?a=bad1&b=bad2")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/gear/compare
# ---------------------------------------------------------------------------

async def test_gear_comparison_ok(client, mock_session):
    """Returns gear change entries between two reports."""
    mock_row = make_row(
        slot=0, old_item_id=12345, old_ilvl=128,
        new_item_id=12346, new_ilvl=132,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/gear/compare?player=Lyro&old=rpt1&new=rpt2"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slot_name"] == "Head"
    assert data[0]["ilvl_delta"] == 4


async def test_gear_comparison_empty(client, mock_session):
    """Returns empty list when no gear data."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/gear/compare?player=Lyro&old=rpt1&new=rpt2"
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_gear_comparison_no_delta_when_old_missing(client, mock_session):
    """ilvl_delta is null when old gear data is missing."""
    mock_row = make_row(
        slot=0, old_item_id=None, old_ilvl=None,
        new_item_id=12346, new_ilvl=132,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/gear/compare?player=Lyro&old=rpt1&new=rpt2"
    )
    data = resp.json()
    assert data[0]["ilvl_delta"] is None
