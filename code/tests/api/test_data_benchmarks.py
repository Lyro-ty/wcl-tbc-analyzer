"""Tests for benchmark and watched guild API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import make_row

SAMPLE_BENCHMARKS = {
    "kill_stats": {"avg_duration_ms": 245000},
    "deaths": {"avg_deaths": 0.3},
    "by_spec": {"Destruction Warlock": {"dps": {"avg_dps": 1420.0}}},
    "consumables": [],
    "composition": [],
}


# ---------------------------------------------------------------------------
# GET /api/data/benchmarks
# ---------------------------------------------------------------------------

async def test_list_benchmarks(client, mock_session):
    """Returns list of benchmark summaries."""
    mock_row = make_row(
        encounter_id=50650,
        encounter_name="Gruul the Dragonkiller",
        sample_size=10,
        computed_at=datetime(2026, 1, 15, 12, 0, 0),
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["encounter_name"] == "Gruul the Dragonkiller"
    assert data[0]["sample_size"] == 10


async def test_list_benchmarks_empty(client, mock_session):
    """Returns empty list when no benchmarks computed."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/benchmarks/{encounter}
# ---------------------------------------------------------------------------

async def test_get_benchmark(client, mock_session):
    """Returns full benchmark for an encounter."""
    mock_row = make_row(
        encounter_id=50650,
        encounter_name="Gruul the Dragonkiller",
        sample_size=10,
        computed_at=datetime(2026, 1, 15, 12, 0, 0),
        benchmarks=SAMPLE_BENCHMARKS,
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/Gruul")
    assert resp.status_code == 200
    data = resp.json()
    assert data["encounter_name"] == "Gruul the Dragonkiller"
    assert data["benchmarks"]["kill_stats"]["avg_duration_ms"] == 245000


async def test_get_benchmark_not_found(client, mock_session):
    """Returns 404 when no benchmark for encounter."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/FakeBoss")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/benchmarks/{encounter}/{class}/{spec}
# ---------------------------------------------------------------------------

async def test_get_spec_benchmark(client, mock_session):
    """Returns spec-specific benchmark data."""
    mock_row = make_row(
        encounter_id=50650,
        encounter_name="Gruul the Dragonkiller",
        sample_size=10,
        computed_at=datetime(2026, 1, 15, 12, 0, 0),
        benchmarks=SAMPLE_BENCHMARKS,
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/Gruul/Warlock/Destruction")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dps"]["avg_dps"] == 1420.0


async def test_get_spec_benchmark_not_found(client, mock_session):
    """Returns 404 when encounter has no benchmark."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/FakeBoss/Warlock/Destruction")
    assert resp.status_code == 404


async def test_get_spec_benchmark_spec_not_found(client, mock_session):
    """Returns 404 when spec not found in benchmark data."""
    mock_row = make_row(
        encounter_id=50650,
        encounter_name="Gruul the Dragonkiller",
        sample_size=10,
        computed_at=datetime(2026, 1, 15, 12, 0, 0),
        benchmarks=SAMPLE_BENCHMARKS,
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/Gruul/Warrior/Arms")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/watched-guilds
# ---------------------------------------------------------------------------

async def test_list_watched_guilds(client, mock_session):
    """Returns list of watched guilds."""
    guild = MagicMock()
    guild.id = 1
    guild.guild_name = "APES"
    guild.wcl_guild_id = 12345
    guild.server_slug = "whitemane"
    guild.server_region = "US"
    guild.is_active = True

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [guild]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/watched-guilds")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["guild_name"] == "APES"
    assert data[0]["wcl_guild_id"] == 12345


async def test_list_watched_guilds_empty(client, mock_session):
    """Returns empty list when no watched guilds."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/watched-guilds")
    assert resp.status_code == 200
    assert resp.json() == []
