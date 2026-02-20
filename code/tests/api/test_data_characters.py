"""Tests for character roster, profile, progression, and regression endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import make_row

# ---------------------------------------------------------------------------
# GET /api/data/characters
# ---------------------------------------------------------------------------

async def test_list_characters_ok(client, mock_session):
    """Returns list of registered characters."""
    mock_row = make_row(
        id=1, name="Lyro", server_slug="whitemane",
        server_region="US", character_class="Warrior", spec="Arms",
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Lyro"
    assert data[0]["character_class"] == "Warrior"


async def test_list_characters_empty(client, mock_session):
    """Returns empty list when no characters registered."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/characters/{name}/profile
# ---------------------------------------------------------------------------

async def test_character_profile_ok(client, mock_session):
    """Returns character profile with aggregate stats."""
    mock_row = make_row(
        id=1, name="Lyro", server_slug="whitemane", server_region="US",
        character_class="Warrior", spec="Arms", total_fights=100,
        total_kills=80, total_deaths=5, avg_dps=2200.0,
        best_dps=3100.0, avg_parse=85.0, best_parse=99.0,
        avg_ilvl=130.0,
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Lyro"
    assert data["best_dps"] == 3100.0
    assert data["total_kills"] == 80


async def test_character_profile_404(client, mock_session):
    """Returns 404 when character not found."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/NoSuch/profile")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/characters/{name}/reports
# ---------------------------------------------------------------------------

async def test_character_reports_ok(client, mock_session):
    """Returns reports containing fights for a character."""
    mock_row = make_row(
        code="abc123", title="Raid Night", guild_name="Guild",
        start_time=1000000, end_time=2000000, fight_count=5,
        kill_count=4, avg_dps=2100.0, avg_parse=82.0, total_deaths=1,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "abc123"


async def test_character_reports_404(client, mock_session):
    """Returns 404 when no reports found for character."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/NoSuch/reports")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/characters/{name}/reports/{code}
# ---------------------------------------------------------------------------

async def test_character_report_detail_ok(client, mock_session):
    """Returns fight-by-fight detail for a character in a report."""
    mock_row = make_row(
        fight_id=1, encounter_name="Gruul the Dragonkiller", kill=True,
        duration_ms=120000, dps=2500.0, hps=0.0,
        parse_percentile=92.0, deaths=0, interrupts=3, dispels=0,
        item_level=130.0, player_class="Warrior", player_spec="Arms",
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/reports/abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["encounter_name"] == "Gruul the Dragonkiller"
    assert data[0]["dps"] == 2500.0


async def test_character_report_detail_404(client, mock_session):
    """Returns 404 when character has no fights in specified report."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/reports/missing")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/characters/{name}/recent-parses
# ---------------------------------------------------------------------------

async def test_character_recent_parses_ok(client, mock_session):
    """Returns recent parse entries for a character."""
    mock_row = make_row(
        encounter_name="Gruul the Dragonkiller", dps=2500.0, hps=0.0,
        parse_percentile=92.0, deaths=0, item_level=130.0,
        player_class="Warrior", player_spec="Arms", kill=True,
        duration_ms=120000, report_code="abc123", fight_id=1,
        report_date=1000000,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/recent-parses")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["encounter_name"] == "Gruul the Dragonkiller"
    assert data[0]["parse_percentile"] == 92.0


async def test_character_recent_parses_empty(client, mock_session):
    """Returns empty list when no recent parses (not 404)."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/recent-parses")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/characters/{name}/personal-bests
# ---------------------------------------------------------------------------

async def test_personal_bests_ok(client, mock_session):
    """Returns personal bests for a character."""
    mock_row = make_row(
        encounter_name="Gruul the Dragonkiller", best_dps=3100.0,
        best_parse=99.0, best_hps=0.0, kill_count=20,
        peak_ilvl=132.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/Lyro/personal-bests")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["best_dps"] == 3100.0
    assert data[0]["kill_count"] == 20


async def test_personal_bests_404(client, mock_session):
    """Returns 404 when no personal bests found."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/characters/NoSuch/personal-bests")
    assert resp.status_code == 404


async def test_personal_bests_with_encounter_filter(client, mock_session):
    """Filters personal bests by encounter name when query param provided."""
    mock_row = make_row(
        encounter_name="Gruul the Dragonkiller", best_dps=3100.0,
        best_parse=99.0, best_hps=0.0, kill_count=20,
        peak_ilvl=132.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/characters/Lyro/personal-bests?encounter=Gruul the Dragonkiller"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


# ---------------------------------------------------------------------------
# GET /api/data/progression/{character}
# ---------------------------------------------------------------------------

async def test_progression_ok(client, mock_session):
    """Returns progression time-series data."""
    mock_row = make_row(
        time=datetime(2026, 1, 15, tzinfo=UTC),
        best_parse=92.0, median_parse=80.0,
        best_dps=2800.0, median_dps=2200.0,
        kill_count=5, avg_deaths=0.2,
        encounter_name="Gruul the Dragonkiller", character_name="Lyro",
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/progression/Lyro?encounter=Gruul the Dragonkiller"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["best_parse"] == 92.0
    assert data[0]["character_name"] == "Lyro"


async def test_progression_404(client, mock_session):
    """Returns 404 when no progression data."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/progression/NoSuch?encounter=Gruul the Dragonkiller"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/regressions
# ---------------------------------------------------------------------------

async def test_regressions_ok(client, mock_session):
    """Returns regression entries for all tracked characters."""
    mock_row = make_row(
        player_name="Lyro", encounter_name="Gruul the Dragonkiller",
        recent_parse=70.0, baseline_parse=90.0,
        recent_dps=2000.0, baseline_dps=2500.0,
        parse_delta=-20.0, dps_delta_pct=-20.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/regressions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["parse_delta"] == -20.0


async def test_regressions_empty(client, mock_session):
    """Returns empty list when no regressions detected (not 404)."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/regressions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_regressions_with_player_filter(client, mock_session):
    """Filters regressions to a specific player."""
    mock_row = make_row(
        player_name="Lyro", encounter_name="Gruul the Dragonkiller",
        recent_parse=70.0, baseline_parse=90.0,
        recent_dps=2000.0, baseline_dps=2500.0,
        parse_delta=-20.0, dps_delta_pct=-20.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/regressions?player=Lyro")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["player_name"] == "Lyro"
