"""Tests for the new ability/buff data API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_session_factory():
    """Factory that returns an AsyncMock session."""
    mock_session = AsyncMock()
    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


@pytest.fixture
def app(mock_session_factory):
    factory, _ = mock_session_factory
    with patch("shukketsu.api.routes.data._session_factory", factory):
        from shukketsu.api.app import create_app
        return create_app()


class TestFightAbilities:
    async def test_returns_abilities(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "metric_type": "damage",
                "ability_name": "Mortal Strike", "spell_id": 12294,
                "total": 50000, "hit_count": 20, "crit_count": 10,
                "crit_pct": 50.0, "pct_of_total": 45.0,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/abilities")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ability_name"] == "Mortal Strike"

    async def test_404_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/abilities")

        assert resp.status_code == 404


class TestPlayerAbilities:
    async def test_returns_player_abilities(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "metric_type": "damage",
                "ability_name": "Whirlwind", "spell_id": 1680,
                "total": 30000, "hit_count": 40, "crit_count": 8,
                "crit_pct": 20.0, "pct_of_total": 30.0,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/abilities/TestWarr")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["player_name"] == "TestWarr"


class TestFightBuffs:
    async def test_returns_buffs(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "metric_type": "buff",
                "ability_name": "Battle Shout", "spell_id": 2048,
                "uptime_pct": 95.0, "stack_count": 0.0,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/buffs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ability_name"] == "Battle Shout"
        assert data[0]["uptime_pct"] == 95.0

    async def test_404_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/buffs")

        assert resp.status_code == 404


class TestAbilitiesAvailable:
    async def test_returns_true_when_data_exists(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(has_data=True)
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/abilities-available")

        assert resp.status_code == 200
        assert resp.json()["has_data"] is True

    async def test_returns_false_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(has_data=False)
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/abilities-available")

        assert resp.status_code == 200
        assert resp.json()["has_data"] is False
