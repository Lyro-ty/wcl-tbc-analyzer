"""Tests for the phase analysis API endpoint."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shukketsu.api.routes.data.fights import router


def _make_row(**kwargs):
    """Create a fake DB row that supports both attribute access and _mapping."""
    row = SimpleNamespace(**kwargs)
    row._mapping = kwargs
    return row


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/data")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _mock_get_db(mock_session):
    """Create a mock get_db dependency that yields the given session."""
    async def _override():
        yield mock_session
    return _override


class TestPhaseEndpoint:
    def test_returns_phases_for_known_encounter(self, app, client):
        mock_rows = [
            _make_row(
                report_code="abc123", fight_id=4,
                duration_ms=300000, kill=True,
                fight_percentage=0.0,
                encounter_name="Kel'Thuzad",
                player_name="Lyro", player_class="Warrior",
                player_spec="Arms", dps=2500.0,
                total_damage=750000, hps=0.0,
                total_healing=0, deaths=0,
                parse_percentile=92.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.api.deps import get_db
        app.dependency_overrides[get_db] = _mock_get_db(mock_session)

        response = client.get("/api/data/reports/abc123/fights/4/phases")
        assert response.status_code == 200
        data = response.json()

        assert data["report_code"] == "abc123"
        assert data["fight_id"] == 4
        assert data["encounter_name"] == "Kel'Thuzad"
        assert data["duration_ms"] == 300000
        assert data["kill"] is True
        assert len(data["phases"]) == 3
        assert data["phases"][0]["name"] == "P1 - Adds"
        assert data["phases"][1]["name"] == "P2 - Active"
        assert data["phases"][2]["name"] == "P3 - Ice Tombs"
        assert len(data["players"]) == 1
        assert data["players"][0]["player_name"] == "Lyro"

        app.dependency_overrides.clear()

    def test_returns_single_phase_for_unknown_encounter(self, app, client):
        mock_rows = [
            _make_row(
                report_code="abc123", fight_id=1,
                duration_ms=120000, kill=True,
                fight_percentage=0.0,
                encounter_name="Unknown Boss",
                player_name="Lyro", player_class="Warrior",
                player_spec="Arms", dps=1800.0,
                total_damage=216000, hps=0.0,
                total_healing=0, deaths=0,
                parse_percentile=80.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.api.deps import get_db
        app.dependency_overrides[get_db] = _mock_get_db(mock_session)

        response = client.get("/api/data/reports/abc123/fights/1/phases")
        assert response.status_code == 200
        data = response.json()

        assert len(data["phases"]) == 1
        assert data["phases"][0]["name"] == "Full Fight"

        app.dependency_overrides.clear()

    def test_returns_404_when_no_data(self, app, client):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.api.deps import get_db
        app.dependency_overrides[get_db] = _mock_get_db(mock_session)

        response = client.get("/api/data/reports/missing/fights/99/phases")
        assert response.status_code == 404

        app.dependency_overrides.clear()

    def test_phase_estimated_times(self, app, client):
        """Phase start/end/duration should be estimated from fight duration."""
        mock_rows = [
            _make_row(
                report_code="abc123", fight_id=4,
                duration_ms=200000, kill=True,
                fight_percentage=0.0,
                encounter_name="Thaddius",
                player_name="Lyro", player_class="Warrior",
                player_spec="Arms", dps=2000.0,
                total_damage=400000, hps=0.0,
                total_healing=0, deaths=0,
                parse_percentile=85.0,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        from shukketsu.api.deps import get_db
        app.dependency_overrides[get_db] = _mock_get_db(mock_session)

        response = client.get("/api/data/reports/abc123/fights/4/phases")
        data = response.json()

        # Thaddius P1: 0.0-0.35 of 200000ms = 0-70000ms
        p1 = data["phases"][0]
        assert p1["estimated_start_ms"] == 0
        assert p1["estimated_end_ms"] == 70000
        assert p1["estimated_duration_ms"] == 70000

        # P2: 0.35-1.0 of 200000ms = 70000-200000ms
        p2 = data["phases"][1]
        assert p2["estimated_start_ms"] == 70000
        assert p2["estimated_end_ms"] == 200000
        assert p2["estimated_duration_ms"] == 130000

        app.dependency_overrides.clear()
