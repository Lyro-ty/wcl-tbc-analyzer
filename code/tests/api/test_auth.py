"""Tests for the API key authentication dependency."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from shukketsu.api.app import create_app
from shukketsu.api.deps import get_db


def _make_app_with_db(mock_session):
    """Create an app with DB overridden but auth NOT overridden."""
    app = create_app()

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    return app


def _mock_session_with_empty_list():
    """Return a mock session that returns an empty fetchall()."""
    session = AsyncMock()
    session.add = MagicMock()    # sync method -- MagicMock not AsyncMock
    session.merge = MagicMock()  # sync method
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    return session


async def test_auth_rejects_when_key_configured_no_key_provided():
    """Request without API key when key is configured returns 401."""
    session = _mock_session_with_empty_list()
    app = _make_app_with_db(session)

    with patch("shukketsu.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "secret-key-123"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/data/reports")

    assert resp.status_code == 401
    assert "Invalid or missing API key" in resp.json()["detail"]
    app.dependency_overrides.clear()


async def test_auth_accepts_valid_header_key():
    """Request with valid X-API-Key header returns 200."""
    session = _mock_session_with_empty_list()
    app = _make_app_with_db(session)

    with patch("shukketsu.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "secret-key-123"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/data/reports",
                headers={"X-API-Key": "secret-key-123"},
            )

    assert resp.status_code == 200
    app.dependency_overrides.clear()


async def test_auth_accepts_valid_query_param():
    """Request with valid api_key query parameter returns 200."""
    session = _mock_session_with_empty_list()
    app = _make_app_with_db(session)

    with patch("shukketsu.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "secret-key-123"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/data/reports?api_key=secret-key-123"
            )

    assert resp.status_code == 200
    app.dependency_overrides.clear()


async def test_auth_rejects_invalid_key():
    """Request with wrong API key returns 401."""
    session = _mock_session_with_empty_list()
    app = _make_app_with_db(session)

    with patch("shukketsu.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "secret-key-123"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/data/reports",
                headers={"X-API-Key": "wrong-key"},
            )

    assert resp.status_code == 401
    app.dependency_overrides.clear()


async def test_auth_disabled_when_no_key_configured():
    """Request without key passes when no API key is configured."""
    session = _mock_session_with_empty_list()
    app = _make_app_with_db(session)

    with patch("shukketsu.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.api_key = ""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/data/reports")

    assert resp.status_code == 200
    app.dependency_overrides.clear()


async def test_auth_header_takes_precedence_over_query():
    """Header key is used even when query param is also present."""
    session = _mock_session_with_empty_list()
    app = _make_app_with_db(session)

    with patch("shukketsu.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.api_key = "secret-key-123"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Correct header + wrong query param should still pass
            # because header_key is checked first (header_key or query_key)
            resp = await client.get(
                "/api/data/reports?api_key=wrong",
                headers={"X-API-Key": "secret-key-123"},
            )

    assert resp.status_code == 200
    app.dependency_overrides.clear()
