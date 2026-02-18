"""Integration test fixtures with real PostgreSQL via testcontainers."""

import os

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from alembic import command


@pytest.fixture(scope="session")
def postgres_container():
    """Spin up a PostgreSQL 16 container for the test session."""
    with PostgresContainer(
        "postgres:16",
        driver=None,
        username="testuser",
        password="testpass",
        dbname="testdb",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def sync_url(postgres_container):
    """Synchronous DB URL for reference (psycopg2-based)."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def async_url(sync_url):
    """Async DB URL for SQLAlchemy async engine."""
    return sync_url.replace("psycopg2", "asyncpg").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(async_url):
    """Run all Alembic migrations against the test DB.

    The alembic env.py uses async_engine_from_config, so we pass the
    asyncpg URL. We also need to run from the project root so the
    relative script_location in alembic.ini resolves correctly.
    """
    # alembic.ini is at the project root; script_location = code/alembic
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    alembic_ini = os.path.join(project_root, "alembic.ini")

    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("sqlalchemy.url", async_url)

    # Alembic resolves script_location relative to the .ini file dir,
    # which is the project root — so "code/alembic" works as-is.
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
async def engine(async_url):
    """Async engine for the test DB."""
    eng = create_async_engine(async_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Async session that rolls back after each test for clean slate."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        # Rollback any uncommitted changes
        await s.rollback()
