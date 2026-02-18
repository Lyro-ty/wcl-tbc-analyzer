"""Tests for report, dashboard, and report-level data endpoints."""

from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import make_row

# ---------------------------------------------------------------------------
# GET /api/data/reports
# ---------------------------------------------------------------------------

async def test_list_reports_ok(client, mock_session):
    """GET /api/data/reports returns list of reports."""
    mock_row = make_row(
        code="abc123", title="Raid Night", guild_name="Test Guild",
        start_time=1000000, end_time=2000000, fight_count=5, boss_count=3,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "abc123"
    assert data[0]["title"] == "Raid Night"
    assert data[0]["boss_count"] == 3


async def test_list_reports_empty(client, mock_session):
    """GET /api/data/reports returns empty list when no reports."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_reports_multiple(client, mock_session):
    """GET /api/data/reports returns multiple reports sorted."""
    rows = [
        make_row(
            code=f"rpt{i}", title=f"Raid {i}", guild_name="G",
            start_time=1000 * i, end_time=2000 * i,
            fight_count=i, boss_count=i,
        )
        for i in range(1, 4)
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["code"] == "rpt1"
    assert data[2]["code"] == "rpt3"


# ---------------------------------------------------------------------------
# GET /api/data/reports/{report_code}/summary
# ---------------------------------------------------------------------------

async def test_report_summary_ok(client, mock_session):
    """GET /api/data/reports/{code}/summary returns raid summary fights."""
    mock_row = make_row(
        fight_id=1, encounter_name="Patchwerk", kill=True,
        duration_ms=120000, player_count=25,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["encounter_name"] == "Patchwerk"
    assert data[0]["kill"] is True
    assert data[0]["duration_ms"] == 120000


async def test_report_summary_404(client, mock_session):
    """GET /api/data/reports/{code}/summary returns 404 when report not found."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/nonexistent/summary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{report_code}/execution
# ---------------------------------------------------------------------------

async def test_report_execution_ok(client, mock_session):
    """GET /api/data/reports/{code}/execution returns boss execution data."""
    mock_row = make_row(
        encounter_name="Patchwerk", fight_id=1, duration_ms=120000,
        player_count=25, total_deaths=2, avg_deaths_per_player=0.08,
        total_interrupts=10, total_dispels=5, raid_avg_dps=1500.0,
        raid_total_dps=37500.0, avg_parse=85.0, avg_ilvl=130.5,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/execution")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["encounter_name"] == "Patchwerk"
    assert data[0]["total_deaths"] == 2


async def test_report_execution_404(client, mock_session):
    """GET /api/data/reports/{code}/execution returns 404 when no kills."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/missing/execution")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{report_code}/speed
# ---------------------------------------------------------------------------

async def test_report_speed_ok(client, mock_session):
    """GET /api/data/reports/{code}/speed returns speed comparison data."""
    mock_row = make_row(
        fight_id=1, encounter_name="Patchwerk", duration_ms=120000,
        player_count=25, total_deaths=2, total_interrupts=10,
        total_dispels=5, avg_dps=1500.0, world_record_ms=80000,
        top10_avg_ms=90000, top100_median_ms=100000,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/speed")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["world_record_ms"] == 80000


async def test_report_speed_404(client, mock_session):
    """GET /api/data/reports/{code}/speed returns 404 when no kills."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/missing/speed")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{report_code}/abilities-available
# ---------------------------------------------------------------------------

async def test_abilities_available_true(client, mock_session):
    """Returns has_data=true when table data exists for report."""
    mock_row = make_row(has_data=True)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/abilities-available")
    assert resp.status_code == 200
    assert resp.json()["has_data"] is True


async def test_abilities_available_false(client, mock_session):
    """Returns has_data=false when no table data for report."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/abilities-available")
    assert resp.status_code == 200
    assert resp.json()["has_data"] is False


# ---------------------------------------------------------------------------
# GET /api/data/reports/{report_code}/events-available
# ---------------------------------------------------------------------------

async def test_events_available_true(client, mock_session):
    """Returns has_data=true when event data exists for report."""
    mock_row = make_row(has_data=True)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/events-available")
    assert resp.status_code == 200
    assert resp.json()["has_data"] is True


async def test_events_available_false(client, mock_session):
    """Returns has_data=false when no event data."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/events-available")
    assert resp.status_code == 200
    assert resp.json()["has_data"] is False


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/wipe-progression/{encounter}
# ---------------------------------------------------------------------------

async def test_wipe_progression_ok(client, mock_session):
    """Returns wipe progression attempts for an encounter."""
    rows = [
        make_row(
            fight_id=i, kill=(i == 3), fight_percentage=100.0 - i * 20.0,
            duration_ms=60000 + i * 10000, player_count=25,
            avg_dps=1000.0 + i * 100, total_deaths=5 - i,
            avg_parse=50.0 + i * 10,
        )
        for i in range(1, 4)
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/wipe-progression/Patchwerk"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[2]["kill"] is True


async def test_wipe_progression_404(client, mock_session):
    """Returns 404 when no attempts found."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/wipe-progression/NoSuchBoss"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/dashboard/stats
# ---------------------------------------------------------------------------

async def test_dashboard_stats_ok(client, mock_session):
    """Returns dashboard aggregates."""
    mock_row = make_row(
        total_reports=10, total_kills=50, total_wipes=20,
        total_characters=5, total_encounters=15,
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reports"] == 10
    assert data["total_kills"] == 50


async def test_dashboard_stats_empty(client, mock_session):
    """Returns zeroed stats when no data."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reports"] == 0
    assert data["total_kills"] == 0


# ---------------------------------------------------------------------------
# GET /api/data/dashboard/recent
# ---------------------------------------------------------------------------

async def test_dashboard_recent_ok(client, mock_session):
    """Returns recent reports for dashboard."""
    mock_row = make_row(
        code="abc123", title="Raid Night", guild_name="Test",
        start_time=1000000, fight_count=5, kill_count=4,
        wipe_count=1, avg_kill_dps=1500.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/dashboard/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "abc123"
    assert data[0]["kill_count"] == 4


async def test_dashboard_recent_empty(client, mock_session):
    """Returns empty list when no recent reports."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/dashboard/recent")
    assert resp.status_code == 200
    assert resp.json() == []
