"""Shared utilities for agent tools -- session management and @db_tool decorator."""

import functools
import inspect
import logging
import re

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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
            logger.exception("Tool error in %s", fn.__name__)
            msg = _sanitize_error(str(e))
            return (
                f"Error in {fn.__name__}: {msg}."
                " Please try a different query."
            )
        finally:
            await session.close()

    # Override the signature so @tool sees parameters without `session`.
    # inspect.signature() checks __signature__ before __wrapped__.
    wrapper.__signature__ = new_sig

    return tool(wrapper)


_CONN_STRING_RE = re.compile(r'postgresql\+?\w*://[^\s]+')
_SQL_DETAIL_RE = re.compile(
    r'\[SQL:.*?\]', flags=re.DOTALL,
)
_SQLA_PREFIX_RE = re.compile(
    r'\([\w.]+\)\s*', flags=re.DOTALL,
)
_TABLE_RE = re.compile(r'relation\s+"[^"]+"')


def _sanitize_error(msg: str) -> str:
    """Strip connection strings, SQL, and table names from error messages."""
    msg = _CONN_STRING_RE.sub('[REDACTED]', msg)
    msg = _SQL_DETAIL_RE.sub('[SQL REDACTED]', msg)
    msg = _SQLA_PREFIX_RE.sub('', msg)
    msg = _TABLE_RE.sub('[table REDACTED]', msg)
    if len(msg) > 200:
        msg = msg[:200] + "..."
    return msg


def _format_duration(ms: int) -> str:
    """Format milliseconds as 'Xm Ys'."""
    seconds = ms // 1000
    return f"{seconds // 60}m {seconds % 60}s"
