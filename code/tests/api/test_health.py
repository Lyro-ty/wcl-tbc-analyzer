from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from shukketsu.api.routes.health import router, set_health_deps


@pytest.fixture(autouse=True)
def _reset_health_deps():
    """Reset module-level globals before each test."""
    set_health_deps(session_factory=None, llm_base_url=None)
    yield
    set_health_deps(session_factory=None, llm_base_url=None)


@pytest.fixture
def app():
    return FastAPI(routes=router.routes)


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    factory = MagicMock(return_value=session)
    return factory


async def test_health_all_ok(app, mock_session_factory):
    """Both DB and LLM reachable returns 200 with status ok."""
    set_health_deps(
        session_factory=mock_session_factory,
        llm_base_url="http://localhost:11434/v1",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("shukketsu.api.routes.health.httpx.AsyncClient", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["llm"] == "ok"
    assert body["version"] == "0.1.0"


async def test_health_db_unreachable(app, mock_session_factory):
    """DB unreachable returns 503 with database error."""
    mock_session_factory.return_value.execute.side_effect = Exception("Connection refused")
    set_health_deps(
        session_factory=mock_session_factory,
        llm_base_url="http://localhost:11434/v1",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("shukketsu.api.routes.health.httpx.AsyncClient", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["llm"] == "ok"


async def test_health_llm_unreachable(app, mock_session_factory):
    """LLM unreachable returns 503 with llm error."""
    set_health_deps(
        session_factory=mock_session_factory,
        llm_base_url="http://localhost:11434/v1",
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("shukketsu.api.routes.health.httpx.AsyncClient", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "ok"
    assert body["llm"] == "error"


async def test_health_llm_non_200(app, mock_session_factory):
    """LLM returns non-200 status code results in 503."""
    set_health_deps(
        session_factory=mock_session_factory,
        llm_base_url="http://localhost:11434/v1",
    )

    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("shukketsu.api.routes.health.httpx.AsyncClient", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["llm"] == "error"


async def test_health_both_unreachable(app, mock_session_factory):
    """Both DB and LLM unreachable returns 503 with both errors."""
    mock_session_factory.return_value.execute.side_effect = Exception("DB down")
    set_health_deps(
        session_factory=mock_session_factory,
        llm_base_url="http://localhost:11434/v1",
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("shukketsu.api.routes.health.httpx.AsyncClient", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["llm"] == "error"


async def test_health_no_deps_configured(app):
    """No deps configured returns not configured status for both."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    # When deps are not configured, endpoint still returns 200
    # (not configured is not the same as unreachable)
    body = resp.json()
    assert body["database"] == "not configured"
    assert body["llm"] == "not configured"


async def test_health_db_session_always_closed(app, mock_session_factory):
    """DB session is closed even when execute raises."""
    mock_session_factory.return_value.execute.side_effect = Exception("DB error")
    set_health_deps(
        session_factory=mock_session_factory,
        llm_base_url=None,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")

    mock_session_factory.return_value.close.assert_awaited_once()
