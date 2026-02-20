"""FastAPI dependency injection providers."""

import asyncio
import hmac
import time
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, APIKeyQuery
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.config import get_settings

# Set during lifespan, read by Depends()
_session_factory = None
_graph = None
_wcl_factory = None

# Cooldown tracking for WCL-calling endpoints
_cooldowns: dict[str, float] = {}
_cooldown_lock = asyncio.Lock()


def set_dependencies(session_factory, graph=None) -> None:
    """Called once during app lifespan startup."""
    global _session_factory, _graph
    _session_factory = session_factory
    _graph = graph


def set_wcl_factory(factory) -> None:
    """Called once during app lifespan startup."""
    global _wcl_factory
    _wcl_factory = factory


def get_wcl_factory():
    """FastAPI dependency -- returns the shared WCL client factory."""
    if _wcl_factory is None:
        raise RuntimeError("WCL factory not initialized")
    return _wcl_factory


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency -- yields a session, auto-closes after request."""
    if _session_factory is None:
        raise RuntimeError("DB not initialized")
    async with _session_factory() as session:
        yield session


def get_graph():
    """FastAPI dependency -- returns the compiled LangGraph."""
    if _graph is None:
        raise RuntimeError("Agent graph not initialized")
    return _graph


# Auth dependencies
_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_query_scheme = APIKeyQuery(name="api_key", auto_error=False)


async def verify_api_key(
    header_key: str | None = Depends(_header_scheme),
    query_key: str | None = Depends(_query_scheme),
) -> None:
    """Rejects requests when API key is configured but not provided."""
    configured_key = get_settings().api_key
    if not configured_key:
        return  # auth disabled when key not set
    provided = header_key or query_key
    if not provided or not hmac.compare_digest(provided, configured_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def cooldown(key: str, seconds: int = 300):
    """FastAPI dependency factory -- rejects calls within cooldown window."""

    async def _check_cooldown() -> None:
        async with _cooldown_lock:
            now = time.monotonic()
            last = _cooldowns.get(key, 0)
            remaining = seconds - (now - last)
            if remaining > 0:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Please wait {int(remaining)}s"
                        " before retrying"
                    ),
                )
            _cooldowns[key] = now

    return Depends(_check_cooldown)
