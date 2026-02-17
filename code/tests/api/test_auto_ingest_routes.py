"""Tests for auto-ingest API routes."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from shukketsu.api.routes.auto_ingest import router, set_service


def _make_app():
    """Create a minimal FastAPI app with the auto-ingest router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


class TestAutoIngestStatusRoute:
    """Tests for GET /api/auto-ingest/status."""

    def test_returns_status(self):
        mock_service = MagicMock()
        mock_service.get_status.return_value = {
            "enabled": True,
            "status": "idle",
            "last_poll": None,
            "last_error": None,
            "guild_id": 123,
            "guild_name": "Test Guild",
            "poll_interval_minutes": 30,
            "stats": {"polls": 0, "reports_ingested": 0, "errors": 0},
        }
        set_service(mock_service)

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/auto-ingest/status")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["status"] == "idle"
        assert data["guild_id"] == 123
        assert data["guild_name"] == "Test Guild"
        assert data["poll_interval_minutes"] == 30
        assert data["stats"]["polls"] == 0

    def test_returns_500_when_service_not_initialized(self):
        set_service(None)

        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/auto-ingest/status")

        assert response.status_code == 500


class TestAutoIngestTriggerRoute:
    """Tests for POST /api/auto-ingest/trigger."""

    def test_trigger_returns_triggered_status(self):
        mock_service = MagicMock()
        mock_service.trigger_now = AsyncMock(
            return_value={"status": "triggered", "message": "Poll started in background"}
        )
        set_service(mock_service)

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/auto-ingest/trigger")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
        assert "message" in data

    def test_trigger_returns_500_when_service_not_initialized(self):
        set_service(None)

        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/auto-ingest/trigger")

        assert response.status_code == 500
