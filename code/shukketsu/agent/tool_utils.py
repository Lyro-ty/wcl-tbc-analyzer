"""Shared utilities for agent tools -- session management and @db_tool decorator."""

import functools
import inspect
import logging
import re

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# All valid tool names — single source of truth for training data pipelines
VALID_TOOLS = frozenset({
    "get_my_performance", "get_top_rankings", "compare_to_top",
    "get_fight_details", "get_progression", "get_deaths_and_mechanics",
    "search_fights", "get_spec_leaderboard", "resolve_my_fights",
    "get_wipe_progression", "get_regressions", "compare_raid_to_top",
    "compare_two_raids", "get_raid_execution", "get_ability_breakdown",
    "get_buff_analysis", "get_overheal_analysis", "get_death_analysis",
    "get_activity_report", "get_cooldown_efficiency", "get_cancelled_casts",
    "get_consumable_check", "get_resource_usage", "get_dot_management",
    "get_rotation_score", "get_gear_changes", "get_phase_analysis",
    "get_enchant_gem_check", "get_encounter_benchmarks", "get_spec_benchmark",
})

# All valid argument names across all tools
VALID_ARGS = frozenset({
    "report_code", "fight_id", "player_name", "encounter_name",
    "class_name", "spec_name", "character_name", "count",
    "bests_only", "report_a", "report_b",
    "report_code_old", "report_code_new",
})

# Phrases indicating the model gave up instead of retrying
GIVE_UP_PHRASES = [
    "i need you to provide",
    "could you provide",
    "please provide",
    "what report",
    "which report",
    "i'm sorry",
    "i apologize",
    "unfortunately, i",
]

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


# ---------------------------------------------------------------------------
# Shared helpers for agent tools
# ---------------------------------------------------------------------------

TABLE_DATA_HINT = (
    "Table data may not have been ingested yet "
    "(use pull-my-logs --with-tables or pull-table-data to fetch it)."
)
EVENT_DATA_HINT = (
    "Event data may not have been ingested yet "
    "(use pull-my-logs --with-events to fetch it)."
)


def wildcard(value: str) -> str:
    """Wrap a value in SQL ILIKE wildcards."""
    return f"%{value}%"


def wildcard_or_none(value: str | None) -> str | None:
    """Wrap in wildcards if truthy, else None (for optional ILIKE params)."""
    if not value or not value.strip():
        return None
    return f"%{value}%"


def grade_above(
    value: float,
    tiers: list[tuple[float, str]],
    default: str,
) -> str:
    """Return the first label whose threshold value >= threshold (higher is better).

    Tiers must be in descending threshold order.
    Example: grade_above(87, [(90, "A"), (75, "B"), (60, "C")], "F") -> "B"
    """
    for threshold, label in tiers:
        if value >= threshold:
            return label
    return default


def grade_below(
    value: float,
    tiers: list[tuple[float, str]],
    default: str,
) -> str:
    """Return the first label whose threshold value < threshold (lower is better).

    Tiers must be in ascending threshold order.
    Example: grade_below(7, [(5, "EXCELLENT"), (10, "GOOD")], "BAD") -> "GOOD"
    """
    for threshold, label in tiers:
        if value < threshold:
            return label
    return default
