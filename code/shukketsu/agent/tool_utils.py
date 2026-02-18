"""Shared utilities for agent tools -- session management and @db_tool decorator."""

import functools
import inspect

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

# Module-level session provider, set during app startup
_session_factory = None


async def _get_session() -> AsyncSession:
    """Get a DB session from the app's session factory."""
    if _session_factory is None:
        raise RuntimeError(
            "Session factory not initialized. Call set_session_factory() first."
        )
    return _session_factory()


def set_session_factory(factory) -> None:
    """Set the session factory. Called once during app lifespan startup."""
    global _session_factory
    _session_factory = factory


def db_tool(fn):
    """Decorator that wraps a tool function with session lifecycle + error handling.

    The decorated function receives a ``session`` as its first argument.
    Session is automatically closed after execution.
    Exceptions are caught and returned as error strings.

    Usage::

        @db_tool
        async def my_tool(session, param: str) -> str:
            result = await session.execute(...)
            return "formatted result"
    """
    # Build a signature without the `session` parameter so @tool
    # generates the correct input schema for the LLM.
    sig = inspect.signature(fn)
    params = [p for name, p in sig.parameters.items() if name != "session"]
    new_sig = sig.replace(parameters=params)

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs) -> str:
        session = await _get_session()
        try:
            return await fn(session, *args, **kwargs)
        except Exception as e:
            return f"Error retrieving data: {e}"
        finally:
            await session.close()

    # Override the signature so @tool sees parameters without `session`.
    # inspect.signature() checks __signature__ before __wrapped__.
    wrapper.__signature__ = new_sig

    return tool(wrapper)


def _format_duration(ms: int) -> str:
    """Format milliseconds as 'Xm Ys'."""
    seconds = ms // 1000
    return f"{seconds // 60}m {seconds % 60}s"
