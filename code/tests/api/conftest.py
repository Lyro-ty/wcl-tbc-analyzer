"""Shared fixtures for API route tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from shukketsu.api.app import create_app
from shukketsu.api.deps import get_db, verify_api_key


def make_row(**kwargs):
    """Create a fake DB row that supports both attribute access and _mapping."""
    row = SimpleNamespace(**kwargs)
    row._mapping = kwargs
    return row


@pytest.fixture
def mock_session():
    """Mock async DB session with sync methods properly mocked."""
    session = AsyncMock()
    session.add = MagicMock()       # sync method -- MagicMock not AsyncMock
    session.merge = MagicMock()     # sync method
    return session


@pytest.fixture
async def client(mock_session):
    """Test client with DI overrides for DB and auth."""
    app = create_app()

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[verify_api_key] = lambda: None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
