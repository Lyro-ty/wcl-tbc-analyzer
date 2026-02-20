# 18-Issue Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 18 security, integrity, and architecture issues across 4 phases with 14 atomic commits.

**Architecture:** Phased approach — quick security wins first, then DB integrity, then refactor, then auth+tests. Each phase builds on the previous. All changes tested before commit.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, pytest, testcontainers

---

## Task 1: Fix path traversal in SPA catchall

**Files:**
- Modify: `code/shukketsu/api/app.py:137-143`
- Test: `code/tests/api/test_health.py`

**Step 1: Write the failing test**

Add to `code/tests/api/test_health.py`:

```python
async def test_spa_path_traversal_blocked():
    """Path traversal attempts serve index.html, not arbitrary files."""
    from shukketsu.api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/../../etc/passwd")
    # Should get index.html (200) or redirect, NOT the passwd file contents
    assert resp.status_code == 200
    assert "root:" not in resp.text
```

**Step 2: Run test to verify it fails or confirms the vulnerability**

Run: `python3 -m pytest code/tests/api/test_health.py::test_spa_path_traversal_blocked -v`

**Step 3: Fix the SPA catchall in app.py**

Replace lines 137-143 in `code/shukketsu/api/app.py`:

```python
        @app.get("/{path:path}")
        async def spa_catchall(path: str):
            """Serve index.html for SPA client-side routing."""
            resolved = (FRONTEND_DIST / path).resolve()
            if resolved.is_relative_to(FRONTEND_DIST.resolve()) and resolved.is_file():
                return FileResponse(resolved)
            return FileResponse(FRONTEND_DIST / "index.html")
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/api/test_health.py::test_spa_path_traversal_blocked -v`
Expected: PASS

**Step 5: Run full test suite to check for regressions**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All 509+ tests pass

---

## Task 2: Fix CORS configuration

**Files:**
- Modify: `code/shukketsu/api/app.py:115-121`

**Step 1: Fix the CORS middleware in app.py**

Replace lines 115-121:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )
```

**Step 2: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

---

## Task 3: Add pool_pre_ping to DB engine

**Files:**
- Modify: `code/shukketsu/db/engine.py:14-20`

**Step 1: Add pool_pre_ping=True**

Replace lines 14-20 in `code/shukketsu/db/engine.py`:

```python
def create_db_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.db.url,
        echo=settings.db.echo,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
        pool_pre_ping=True,
    )
```

**Step 2: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

---

## Task 4: Add auto-ingest concurrent task guard

**Files:**
- Modify: `code/shukketsu/pipeline/auto_ingest.py:166-169`
- Test: `code/tests/pipeline/test_auto_ingest.py`

**Step 1: Write the failing test**

Add to `code/tests/pipeline/test_auto_ingest.py`:

```python
async def test_trigger_now_rejects_concurrent():
    """Second trigger_now call returns already_running while first is active."""
    settings = _make_settings()
    wcl = AsyncMock()
    service = AutoIngestService(settings, AsyncMock(), _make_wcl_factory(wcl))

    # Simulate an in-progress trigger task
    never_done = asyncio.Future()
    service._trigger_task = asyncio.ensure_future(never_done)

    result = await service.trigger_now()
    assert result["status"] == "already_running"

    # Clean up
    never_done.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await never_done
```

Requires adding `import asyncio` and `import contextlib` to test file imports.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py::test_trigger_now_rejects_concurrent -v`
Expected: FAIL (no guard exists yet)

**Step 3: Add the guard to trigger_now()**

Replace lines 166-169 in `code/shukketsu/pipeline/auto_ingest.py`:

```python
    async def trigger_now(self) -> dict:
        """Manual trigger, runs poll in background."""
        if self._trigger_task and not self._trigger_task.done():
            return {"status": "already_running", "message": "Poll already in progress"}
        self._trigger_task = asyncio.create_task(self._poll_once())
        return {"status": "triggered", "message": "Poll started in background"}
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py::test_trigger_now_rejects_concurrent -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

**Step 6: Commit Phase 1**

```bash
git add code/shukketsu/api/app.py code/shukketsu/db/engine.py code/shukketsu/pipeline/auto_ingest.py code/tests/api/test_health.py code/tests/pipeline/test_auto_ingest.py
git commit -m "$(cat <<'EOF'
fix: path traversal, CORS, pool_pre_ping, auto-ingest guard

Phase 1 security quick wins:
- SPA catchall validates resolved path stays within FRONTEND_DIST
- CORS locked to localhost origins, credentials disabled
- pool_pre_ping=True on async engine for stale connection recovery
- Auto-ingest trigger_now() rejects concurrent polls

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Alembic migration for CASCADE DELETE + CHECK constraints

**Files:**
- Create: `code/alembic/versions/014_add_cascades_and_checks.py`

**Step 1: Create the migration file**

Create `code/alembic/versions/014_add_cascades_and_checks.py`:

```python
"""add cascade deletes and check constraints

Revision ID: 014
Revises: 013
Create Date: 2026-02-17

"""
from collections.abc import Sequence

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All FK columns that need CASCADE DELETE, as (table, constraint_name, col, ref_table, ref_col)
_FK_CASCADES = [
    ("fights", "fights_report_code_fkey", ["report_code"], "reports", ["code"]),
    ("fights", "fights_encounter_id_fkey", ["encounter_id"], "encounters", ["id"]),
    ("fight_performances", "fight_performances_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("ability_metrics", "ability_metrics_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("buff_uptimes", "buff_uptimes_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("death_details", "death_details_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("cast_events", "cast_events_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("cast_metrics", "cast_metrics_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("cooldown_usage", "cooldown_usage_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("cancelled_casts", "cancelled_casts_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("resource_snapshots", "resource_snapshots_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("fight_consumables", "fight_consumables_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("gear_snapshots", "gear_snapshots_fight_id_fkey", ["fight_id"], "fights", ["id"]),
    ("top_rankings", "top_rankings_encounter_id_fkey", ["encounter_id"], "encounters", ["id"]),
    ("speed_rankings", "speed_rankings_encounter_id_fkey", ["encounter_id"], "encounters", ["id"]),
    ("progression_snapshots", "progression_snapshots_character_id_fkey", ["character_id"], "my_characters", ["id"]),
    ("progression_snapshots", "progression_snapshots_encounter_id_fkey", ["encounter_id"], "encounters", ["id"]),
]

# CHECK constraints: (table, constraint_name, expression)
_CHECKS = [
    ("fight_performances", "ck_fp_parse_pct", "parse_percentile IS NULL OR (parse_percentile >= 0 AND parse_percentile <= 100)"),
    ("fight_performances", "ck_fp_ilvl_parse_pct", "ilvl_parse_percentile IS NULL OR (ilvl_parse_percentile >= 0 AND ilvl_parse_percentile <= 100)"),
    ("fight_performances", "ck_fp_dps_pos", "dps >= 0"),
    ("cast_metrics", "ck_cm_gcd_pct", "gcd_uptime_pct >= 0 AND gcd_uptime_pct <= 100"),
    ("buff_uptimes", "ck_bu_uptime_pct", "uptime_pct >= 0 AND uptime_pct <= 100"),
    ("cooldown_usage", "ck_cu_eff_pct", "efficiency_pct >= 0 AND efficiency_pct <= 100"),
    ("cancelled_casts", "ck_cc_cancel_pct", "cancel_pct >= 0 AND cancel_pct <= 100"),
    ("resource_snapshots", "ck_rs_zero_pct", "time_at_zero_pct >= 0 AND time_at_zero_pct <= 100"),
]


def upgrade() -> None:
    # Replace all FKs with CASCADE DELETE versions
    for table, constraint, cols, ref_table, ref_cols in _FK_CASCADES:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table, cols, ref_cols, ondelete="CASCADE"
        )

    # Add CHECK constraints
    for table, name, expr in _CHECKS:
        op.create_check_constraint(name, table, expr)


def downgrade() -> None:
    # Remove CHECK constraints
    for table, name, _expr in reversed(_CHECKS):
        op.drop_constraint(name, table, type_="check")

    # Revert FKs to non-CASCADE
    for table, constraint, cols, ref_table, ref_cols in reversed(_FK_CASCADES):
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table, cols, ref_cols
        )
```

**Step 2: Verify migration syntax**

Run: `python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('m', 'code/alembic/versions/014_add_cascades_and_checks.py'); m = importlib.util.module_from_spec(spec); print('Syntax OK')"`
Expected: "Syntax OK"

---

## Task 6: Update ORM models with ondelete CASCADE + CheckConstraint

**Files:**
- Modify: `code/shukketsu/db/models.py`

**Step 1: Add `ondelete="CASCADE"` to all FK declarations and CheckConstraint to relevant tables**

In `models.py`, update every `ForeignKey()` call to include `ondelete="CASCADE"`. Add `CheckConstraint` imports and `__table_args__` entries.

Key changes:
- `from sqlalchemy import CheckConstraint` to imports
- `Fight.report_code`: `ForeignKey("reports.code", ondelete="CASCADE")`
- `Fight.encounter_id`: `ForeignKey("encounters.id", ondelete="CASCADE")`
- `FightPerformance.fight_id`: `ForeignKey("fights.id", ondelete="CASCADE")`
- Add `CheckConstraint` for parse_percentile, dps, gcd_uptime_pct, uptime_pct, efficiency_pct, cancel_pct, time_at_zero_pct
- Same pattern for all 13 child tables with fight_id FK
- `TopRanking.encounter_id`, `SpeedRanking.encounter_id`: CASCADE
- `ProgressionSnapshot.character_id`, `ProgressionSnapshot.encounter_id`: CASCADE

**Step 2: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass (model changes are declaration-only)

**Step 3: Commit**

```bash
git add code/alembic/versions/014_add_cascades_and_checks.py code/shukketsu/db/models.py
git commit -m "$(cat <<'EOF'
feat: CASCADE DELETE on all FKs + CHECK constraints on percentages

Alembic 014: replaces 17 FKs with CASCADE DELETE versions and adds
8 CHECK constraints for bounded numeric columns (parse %, GCD %, etc.).
ORM models updated to match.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Transaction boundaries in ingest pipeline

**Files:**
- Modify: `code/shukketsu/pipeline/ingest.py`
- Modify: `code/shukketsu/pipeline/auto_ingest.py:146-153`
- Modify: `code/shukketsu/scripts/pull_my_logs.py` (caller pattern)
- Test: `code/tests/pipeline/test_ingest.py`

**Step 1: Update IngestResult dataclass**

In `code/shukketsu/pipeline/ingest.py`, update the `IngestResult` dataclass to track enrichment errors:

```python
@dataclass
class IngestResult:
    fights: int
    performances: int
    table_rows: int = 0
    event_rows: int = 0
    snapshots: int = 0
    enrichment_errors: list[str] | None = None
```

**Step 2: Restructure ingest_report() — enrichment errors tracked, not swallowed**

Replace the event ingest section (lines 204-231) to track errors via enrichment_errors list instead of bare try/except that continues silently. Keep the enrichment try/except blocks but populate `enrichment_errors` list and log properly.

Move the progression snapshot call OUT of ingest_report() — it should be called by the caller in a separate transaction after commit.

**Step 3: Update auto_ingest.py caller to use session.begin()**

Replace lines 147-153 in auto_ingest.py:

```python
                try:
                    async with self._session_factory() as session:
                        async with session.begin():
                            result = await ingest_report(
                                wcl, session, code,
                                ingest_tables=cfg.with_tables,
                                ingest_events=cfg.with_events,
                            )
                    # Snapshot in separate transaction after successful commit
                    async with self._session_factory() as session:
                        async with session.begin():
                            await snapshot_all_characters(session)
```

**Step 4: Update tests and run**

Run: `python3 -m pytest code/tests/pipeline/test_ingest.py -v`
Expected: All ingest tests pass

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

---

## Task 8: Fix silent exception swallowing in pipeline modules

**Files:**
- Modify: `code/shukketsu/pipeline/table_data.py`
- Modify: `code/shukketsu/pipeline/death_events.py`
- Modify: `code/shukketsu/pipeline/combatant_info.py`
- Modify: `code/shukketsu/pipeline/cast_events.py`
- Modify: `code/shukketsu/pipeline/resource_events.py`
- Modify: `code/shukketsu/pipeline/rankings.py`
- Modify: `code/shukketsu/pipeline/speed_rankings.py`

**Step 1: Audit and fix each module**

For each module, find `except Exception` blocks and apply the rule:
- **If it's a per-item error in a loop** (e.g., parsing a single fight): log with `logger.error()` including the item context (fight_id, report_code), then continue the loop
- **If it's a top-level function error**: let it propagate (remove the try/except)
- **Every except block MUST have `logger.error()` or `logger.exception()`** — never silently pass

Pattern for per-item errors:
```python
except Exception:
    logger.exception("Failed to process %s for fight %d in %s", data_type, fight.fight_id, report_code)
    # continue to next fight
```

Pattern for top-level errors (remove try/except, let caller handle):
```python
# BEFORE:
try:
    result = await dangerous_operation()
except Exception:
    pass  # silent!

# AFTER:
result = await dangerous_operation()  # propagate to caller
```

**Step 2: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

**Step 3: Commit**

```bash
git add code/shukketsu/pipeline/
git commit -m "$(cat <<'EOF'
fix: transaction boundaries + structured error tracking in pipeline

- ingest_report() no longer commits; caller owns transaction via session.begin()
- Enrichment errors tracked in IngestResult.enrichment_errors (not swallowed)
- All pipeline except blocks now log with context (module, fight_id, report_code)
- Progression snapshots moved to separate post-commit transaction

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Streaming fetch_all_events + LIMIT on unbounded queries

**Files:**
- Modify: `code/shukketsu/wcl/events.py`
- Modify: `code/shukketsu/pipeline/cast_events.py` (caller)
- Modify: `code/shukketsu/pipeline/death_events.py` (caller)
- Modify: `code/shukketsu/pipeline/resource_events.py` (caller)
- Modify: `code/shukketsu/db/queries.py`
- Test: `code/tests/wcl/test_events.py`

**Step 1: Convert fetch_all_events to async generator**

Replace the function in `code/shukketsu/wcl/events.py`:

```python
async def fetch_all_events(
    wcl,
    report_code: str,
    start_time: float,
    end_time: float,
    data_type: str,
    source_id: int | None = None,
):
    """Yield event pages as lists instead of accumulating all in memory.

    Yields:
        list[dict]: Each page of events (~300 per page).
    """
    query = REPORT_EVENTS.replace("RATE_LIMIT", RATE_LIMIT_FRAG)
    current_start = start_time
    total_fetched = 0

    while True:
        variables: dict = {
            "code": report_code,
            "startTime": current_start,
            "endTime": end_time,
            "dataType": data_type,
        }
        if source_id is not None:
            variables["sourceID"] = source_id

        raw = await wcl.query(query, variables=variables)
        events_data = raw["reportData"]["report"]["events"]

        page_events = events_data.get("data", [])
        total_fetched += len(page_events)
        if page_events:
            yield page_events

        next_page = events_data.get("nextPageTimestamp")
        if next_page is None:
            break

        current_start = next_page
        logger.debug(
            "Events pagination: fetched %d events so far, next page at %d",
            total_fetched, next_page,
        )

    logger.info(
        "Fetched %d %s events for %s (%.0f-%.0f)",
        total_fetched, data_type, report_code, start_time, end_time,
    )
```

**Step 2: Update callers to use `async for page`**

In each caller (cast_events.py, death_events.py, resource_events.py), replace:
```python
all_events = await fetch_all_events(wcl, ...)
for event in all_events:
    ...
```
With:
```python
async for page in fetch_all_events(wcl, ...):
    for event in page:
        ...
```

**Step 3: Update event tests**

In `code/tests/wcl/test_events.py`, update tests to use `async for` pattern instead of `await`.

**Step 4: Add LIMIT to unbounded queries**

In `code/shukketsu/db/queries.py`, add LIMIT clauses:
- `FIGHT_DETAILS`: add `LIMIT 50` after `ORDER BY fp.dps DESC` (line 69)
- `PROGRESSION`: add `LIMIT 100` after `ORDER BY ps.time ASC` (line 81)
- `SPEC_LEADERBOARD`: add `LIMIT 50` after its ORDER BY
- `RAID_EXECUTION_SUMMARY`: add `LIMIT 25` after its ORDER BY

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

**Step 6: Commit**

```bash
git add code/shukketsu/wcl/events.py code/shukketsu/pipeline/cast_events.py code/shukketsu/pipeline/death_events.py code/shukketsu/pipeline/resource_events.py code/shukketsu/db/queries.py code/tests/wcl/test_events.py
git commit -m "$(cat <<'EOF'
feat: streaming events pagination + LIMIT on unbounded queries

- fetch_all_events() is now an async generator yielding per-page
- Memory usage drops from O(all events) to O(one page ~300 events)
- Added LIMIT to FIGHT_DETAILS (50), PROGRESSION (100),
  SPEC_LEADERBOARD (50), RAID_EXECUTION_SUMMARY (25)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Create @db_tool decorator

**Files:**
- Create: `code/shukketsu/agent/tool_utils.py`
- Test: `code/tests/agent/test_tool_utils.py`

**Step 1: Write the test**

Create `code/tests/agent/test_tool_utils.py`:

```python
"""Tests for the @db_tool decorator."""

from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.agent.tool_utils import db_tool, set_session_factory


async def test_db_tool_provides_session_and_closes():
    """db_tool injects a session and closes it after execution."""
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    factory = MagicMock(return_value=mock_session)
    set_session_factory(factory)

    @db_tool
    async def my_tool(session, name: str) -> str:
        """A test tool."""
        return f"Hello {name}"

    result = await my_tool.ainvoke({"name": "World"})
    assert result == "Hello World"
    mock_session.close.assert_awaited_once()


async def test_db_tool_returns_error_on_exception():
    """db_tool catches exceptions and returns error string."""
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    factory = MagicMock(return_value=mock_session)
    set_session_factory(factory)

    @db_tool
    async def failing_tool(session) -> str:
        """A tool that fails."""
        raise ValueError("something broke")

    result = await failing_tool.ainvoke({})
    assert "Error retrieving data: something broke" in result
    mock_session.close.assert_awaited_once()


async def test_db_tool_closes_session_on_error():
    """Session is closed even when the tool raises."""
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    factory = MagicMock(return_value=mock_session)
    set_session_factory(factory)

    @db_tool
    async def error_tool(session) -> str:
        """A tool that errors."""
        raise RuntimeError("fail")

    await error_tool.ainvoke({})
    mock_session.close.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/agent/test_tool_utils.py -v`
Expected: FAIL (module doesn't exist yet)

**Step 3: Create tool_utils.py**

Create `code/shukketsu/agent/tool_utils.py`:

```python
"""Shared utilities for agent tools — session management and @db_tool decorator."""

import functools

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

    The decorated function receives a `session` as its first argument.
    Session is automatically closed after execution.
    Exceptions are caught and returned as error strings.
    """
    @tool
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs) -> str:
        session = await _get_session()
        try:
            return await fn(session, *args, **kwargs)
        except Exception as e:
            return f"Error retrieving data: {e}"
        finally:
            await session.close()

    return wrapper


def _format_duration(ms: int) -> str:
    """Format milliseconds as 'Xm Ys'."""
    seconds = ms // 1000
    return f"{seconds // 60}m {seconds % 60}s"
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest code/tests/agent/test_tool_utils.py -v`
Expected: PASS

---

## Task 11: Split tools.py into domain modules

**Files:**
- Create: `code/shukketsu/agent/tools/__init__.py`
- Create: `code/shukketsu/agent/tools/player_tools.py`
- Create: `code/shukketsu/agent/tools/raid_tools.py`
- Create: `code/shukketsu/agent/tools/table_tools.py`
- Create: `code/shukketsu/agent/tools/event_tools.py`
- Delete: `code/shukketsu/agent/tools.py` (replaced by tools/ package)
- Modify: `code/shukketsu/agent/graph.py` (update import)
- Modify: `code/shukketsu/api/app.py` (update import)

**Step 1: Create the tools/ package directory and __init__.py**

Move each tool function into its domain module. Each module imports from `tool_utils` and `db.queries`:

```python
# player_tools.py — all 11 player-level tools
from shukketsu.agent.tool_utils import _format_duration, db_tool
from shukketsu.db import queries as q
```

**Step 2: Create __init__.py that re-exports ALL_TOOLS**

```python
"""Agent tools package — re-exports ALL_TOOLS for graph binding."""

from shukketsu.agent.tools.event_tools import (
    get_activity_report,
    get_cancelled_casts,
    get_consumable_check,
    get_cooldown_efficiency,
    get_cooldown_windows,
    get_death_analysis,
    get_dot_management,
    get_enchant_gem_check,
    get_gear_changes,
    get_phase_analysis,
    get_resource_usage,
    get_rotation_score,
)
from shukketsu.agent.tools.player_tools import (
    compare_to_top,
    get_deaths_and_mechanics,
    get_fight_details,
    get_my_performance,
    get_progression,
    get_regressions,
    get_spec_leaderboard,
    get_top_rankings,
    get_wipe_progression,
    resolve_my_fights,
    search_fights,
)
from shukketsu.agent.tools.raid_tools import (
    compare_raid_to_top,
    compare_two_raids,
    get_raid_execution,
)
from shukketsu.agent.tools.table_tools import (
    get_ability_breakdown,
    get_buff_analysis,
    get_overheal_analysis,
    get_trinket_performance,
)

ALL_TOOLS = [
    # Player tools
    get_my_performance, get_top_rankings, compare_to_top, get_fight_details,
    get_progression, get_deaths_and_mechanics, search_fights,
    get_spec_leaderboard, resolve_my_fights, get_wipe_progression,
    get_regressions,
    # Raid tools
    compare_raid_to_top, compare_two_raids, get_raid_execution,
    # Table-data tools
    get_ability_breakdown, get_buff_analysis, get_overheal_analysis,
    get_trinket_performance,
    # Event-data tools
    get_death_analysis, get_activity_report, get_cooldown_efficiency,
    get_cooldown_windows, get_cancelled_casts, get_consumable_check,
    get_resource_usage, get_dot_management, get_rotation_score,
    get_gear_changes, get_phase_analysis, get_enchant_gem_check,
]
```

**Step 3: Update imports in graph.py and app.py**

`graph.py`: Change `from shukketsu.agent.tools import ALL_TOOLS` (should work as-is since tools/ is now a package)

`app.py`: Change `from shukketsu.agent.tools import ALL_TOOLS, set_session_factory` to:
```python
from shukketsu.agent.tools import ALL_TOOLS
from shukketsu.agent.tool_utils import set_session_factory
```

**Step 4: Convert each tool to use @db_tool**

For each tool, replace the boilerplate pattern:
```python
# BEFORE:
@tool
async def some_tool(param: str) -> str:
    """Docstring."""
    session = await _get_session()
    try:
        # ... query logic ...
        return result
    except Exception as e:
        return f"Error retrieving data: {e}"
    finally:
        await session.close()

# AFTER:
@db_tool
async def some_tool(session, param: str) -> str:
    """Docstring."""
    # ... query logic ...
    return result
```

**Step 5: Run all tool tests**

Run: `python3 -m pytest code/tests/agent/ -v`
Expected: All agent tests pass

**Step 6: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

**Step 7: Commit**

```bash
git add code/shukketsu/agent/ code/tests/agent/
git commit -m "$(cat <<'EOF'
refactor: split tools.py into domain modules with @db_tool decorator

- New tool_utils.py with @db_tool decorator, session factory, helpers
- tools/ package: player_tools (11), raid_tools (3), table_tools (4), event_tools (12)
- ~330 lines of duplicated boilerplate eliminated
- ALL_TOOLS re-exported from tools/__init__.py

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Split data.py + FastAPI DI

**Files:**
- Modify: `code/shukketsu/api/deps.py`
- Create: `code/shukketsu/api/routes/data/__init__.py`
- Create: `code/shukketsu/api/routes/data/reports.py`
- Create: `code/shukketsu/api/routes/data/fights.py`
- Create: `code/shukketsu/api/routes/data/characters.py`
- Create: `code/shukketsu/api/routes/data/rankings.py`
- Create: `code/shukketsu/api/routes/data/comparison.py`
- Create: `code/shukketsu/api/routes/data/events.py`
- Delete: `code/shukketsu/api/routes/data.py` (replaced by data/ package)
- Modify: `code/shukketsu/api/app.py`

**Step 1: Write deps.py with DI providers**

Replace `code/shukketsu/api/deps.py`:

```python
"""FastAPI dependency injection providers."""

import time
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, APIKeyQuery
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.config import get_settings

# Set during lifespan, read by Depends()
_session_factory = None
_graph = None

# Cooldown tracking for WCL-calling endpoints
_cooldowns: dict[str, float] = {}


def set_dependencies(session_factory, graph=None) -> None:
    """Called once during app lifespan startup."""
    global _session_factory, _graph
    _session_factory = session_factory
    _graph = graph


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency — yields a session, auto-closes after request."""
    if _session_factory is None:
        raise RuntimeError("DB not initialized")
    async with _session_factory() as session:
        yield session


def get_graph():
    """FastAPI dependency — returns the compiled LangGraph."""
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
    """Rejects requests when API key is configured but not provided/matched."""
    configured_key = get_settings().app.api_key
    if not configured_key:
        return  # auth disabled when key not set
    provided = header_key or query_key
    if not provided or provided != configured_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def cooldown(key: str, seconds: int = 300):
    """FastAPI dependency factory — rejects calls within cooldown window."""
    async def _check_cooldown() -> None:
        now = time.monotonic()
        last = _cooldowns.get(key, 0)
        remaining = seconds - (now - last)
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {int(remaining)}s before retrying",
            )
        _cooldowns[key] = now
    return Depends(_check_cooldown)
```

**Step 2: Split data.py into domain route modules**

Each module follows this pattern:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import get_db
from shukketsu.db import queries as q

router = APIRouter()

@router.get("/reports", response_model=list[ReportSummary])
async def list_reports(session: AsyncSession = Depends(get_db)):
    result = await session.execute(q.REPORTS_LIST)
    rows = result.fetchall()
    return [ReportSummary(**dict(r._mapping)) for r in rows]
```

No more manual `_get_session()` / `finally: await session.close()` — the DI context manager handles it.

**Step 3: Create data/__init__.py that combines sub-routers**

```python
"""Data API routes package."""

from fastapi import APIRouter

from shukketsu.api.routes.data.characters import router as characters_router
from shukketsu.api.routes.data.comparison import router as comparison_router
from shukketsu.api.routes.data.events import router as events_router
from shukketsu.api.routes.data.fights import router as fights_router
from shukketsu.api.routes.data.rankings import router as rankings_router
from shukketsu.api.routes.data.reports import router as reports_router

router = APIRouter(prefix="/api/data", tags=["data"])

router.include_router(reports_router)
router.include_router(fights_router)
router.include_router(characters_router)
router.include_router(rankings_router)
router.include_router(comparison_router)
router.include_router(events_router)
```

**Step 4: Update app.py lifespan and imports**

```python
from shukketsu.agent.tool_utils import set_session_factory
from shukketsu.api.deps import set_dependencies

# In lifespan:
set_session_factory(session_factory)  # for agent tools
set_dependencies(session_factory=session_factory, graph=graph)  # for routes
```

Remove old `set_data_session_factory` import and call.

**Step 5: Update app.py to apply auth at router level**

```python
from shukketsu.api.deps import verify_api_key

app.include_router(data_router, dependencies=[Depends(verify_api_key)])
app.include_router(analyze_router, dependencies=[Depends(verify_api_key)])
app.include_router(auto_ingest_router, dependencies=[Depends(verify_api_key)])
# health_router — no auth
```

**Step 6: Add api_key to AppConfig**

In `code/shukketsu/config.py`, update AppConfig:

```python
class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = ""  # empty = auth disabled
```

**Step 7: Apply cooldown guards to expensive endpoints**

In `data/reports.py`:
```python
from shukketsu.api.deps import cooldown

@router.post("/ingest", dependencies=[cooldown("ingest", 120)])
async def ingest_report_endpoint(...):
```

In `data/rankings.py`:
```python
@router.post("/rankings/refresh", dependencies=[cooldown("rankings_refresh", 300)])
...
@router.post("/speed-rankings/refresh", dependencies=[cooldown("speed_rankings_refresh", 300)])
```

**Step 8: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

**Step 9: Commit**

```bash
git add code/shukketsu/api/ code/shukketsu/config.py
git commit -m "$(cat <<'EOF'
refactor: split data.py into domain modules + FastAPI DI + auth + cooldowns

- deps.py: get_db(), verify_api_key(), cooldown() dependencies
- data/ package: reports, fights, characters, rankings, comparison, events
- Routes use Depends(get_db) instead of module globals
- API key auth (APP__API_KEY) on data/analyze/auto-ingest routers
- Cooldown guards on ingest (120s) and rankings refresh (300s) endpoints

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Route tests for data endpoints

**Files:**
- Modify: `code/tests/api/conftest.py` (create shared fixtures)
- Create: `code/tests/api/test_reports.py`
- Create: `code/tests/api/test_fights.py`
- Create: `code/tests/api/test_characters.py`
- Create: `code/tests/api/test_rankings.py`
- Create: `code/tests/api/test_comparison.py`
- Create: `code/tests/api/test_events_data.py`
- Create: `code/tests/api/test_auth.py`

**Step 1: Create shared test fixtures in conftest.py**

Update `code/tests/api/conftest.py` (currently empty __init__.py exists):

```python
"""Shared fixtures for API route tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from shukketsu.api.app import create_app
from shukketsu.api.deps import get_db, set_dependencies, verify_api_key


@pytest.fixture
def mock_session():
    """Mock async DB session with sync methods properly mocked."""
    session = AsyncMock()
    session.add = MagicMock()  # sync method — MagicMock not AsyncMock
    session.merge = MagicMock()  # sync method
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
```

**Step 2: Write tests for each route module**

Each test file follows the pattern:
```python
async def test_list_reports_ok(client, mock_session):
    """GET /api/data/reports returns list of reports."""
    mock_row = MagicMock()
    mock_row._mapping = {"code": "abc123", "title": "Raid Night", ...}
    mock_session.execute.return_value.fetchall.return_value = [mock_row]

    resp = await client.get("/api/data/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "abc123"


async def test_list_reports_empty(client, mock_session):
    """GET /api/data/reports returns empty list when no reports."""
    mock_session.execute.return_value.fetchall.return_value = []
    resp = await client.get("/api/data/reports")
    assert resp.status_code == 200
    assert resp.json() == []
```

Write ~10-15 tests per file covering happy path, 404, and edge cases.

**Step 3: Write auth tests**

```python
async def test_auth_rejects_missing_key(mock_session):
    """Requests without API key are rejected when key is configured."""
    # Test with API key configured but not provided
    ...

async def test_auth_accepts_valid_header(mock_session):
    """Requests with valid X-API-Key header are accepted."""
    ...

async def test_auth_disabled_when_no_key_configured(mock_session):
    """All requests pass when APP__API_KEY is empty."""
    ...
```

**Step 4: Run all new tests**

Run: `python3 -m pytest code/tests/api/ -v`
Expected: All pass

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -x -q`
Expected: All tests pass

**Step 6: Commit**

```bash
git add code/tests/api/
git commit -m "$(cat <<'EOF'
test: add route tests for data endpoints + auth tests

~80-100 new tests covering:
- All data route modules (reports, fights, characters, rankings, comparison, events)
- API key auth acceptance/rejection
- Happy paths, 404s, and edge cases

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Integration tests with Docker testcontainers

**Files:**
- Create: `code/tests/integration/__init__.py`
- Create: `code/tests/integration/conftest.py`
- Create: `code/tests/integration/test_cascade_deletes.py`
- Create: `code/tests/integration/test_constraints.py`
- Create: `code/tests/integration/test_queries.py`

**Step 1: Add testcontainers to dev dependencies**

Run: `pip install --break-system-packages testcontainers[postgres] psycopg2-binary`

Add to `pyproject.toml` dev dependencies.

**Step 2: Create integration test conftest**

```python
"""Integration test fixtures with real PostgreSQL via testcontainers."""

import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Run Alembic migrations synchronously
from alembic.config import Config
from alembic import command


@pytest.fixture(scope="session")
def postgres_container():
    """Spin up a PostgreSQL 16 container for the test session."""
    with PostgresContainer("postgres:16", driver="psycopg2") as pg:
        yield pg


@pytest.fixture(scope="session")
def sync_url(postgres_container):
    """Synchronous DB URL for Alembic migrations."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def async_url(sync_url):
    """Async DB URL for SQLAlchemy async engine."""
    return sync_url.replace("psycopg2", "asyncpg")


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(sync_url):
    """Run all Alembic migrations against the test DB."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
async def session(async_url):
    """Async session that rolls back after each test."""
    engine = create_async_engine(async_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        async with s.begin():
            yield s
            await s.rollback()
    await engine.dispose()
```

**Step 3: Write cascade delete tests**

```python
@pytest.mark.integration
async def test_delete_report_cascades_to_fights(session):
    """Deleting a report cascades to its fights."""
    # Insert encounter, report, fight
    # Delete report
    # Verify fight is gone
```

**Step 4: Write CHECK constraint tests**

```python
@pytest.mark.integration
async def test_parse_percentile_rejects_over_100(session):
    """CHECK constraint rejects parse_percentile > 100."""
    # Insert fight_performance with parse_percentile=150
    # Expect IntegrityError
```

**Step 5: Write query syntax tests**

```python
@pytest.mark.integration
async def test_all_queries_execute(session):
    """Every raw SQL query in queries.py executes without syntax errors."""
    # Execute each query with dummy params
    # Verify no SQL syntax errors (empty result is fine)
```

**Step 6: Add pytest marker**

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = ["integration: requires Docker PostgreSQL (testcontainers)"]
```

**Step 7: Run integration tests**

Run: `python3 -m pytest code/tests/integration/ -v -m integration`
Expected: All pass

**Step 8: Verify unit tests still pass**

Run: `python3 -m pytest code/tests/ -x -q --ignore=code/tests/integration/`
Expected: All unit tests still pass

**Step 9: Commit**

```bash
git add code/tests/integration/ pyproject.toml
git commit -m "$(cat <<'EOF'
test: add integration tests with Docker testcontainers

~25-30 integration tests covering:
- CASCADE DELETE behavior (report → fights → performances)
- CHECK constraints (reject invalid percentages/negative values)
- Raw SQL query syntax validation (all queries.py queries execute)
- Case-insensitive ILIKE matching

Run: pytest code/tests/integration/ -v -m integration

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Verification Checklist

After all 14 tasks are complete:

- [ ] `python3 -m pytest code/tests/ -x -q --ignore=code/tests/integration/` — all unit tests pass
- [ ] `python3 -m pytest code/tests/integration/ -v -m integration` — all integration tests pass
- [ ] `python3 -m ruff check code/` — no lint errors
- [ ] `git log --oneline -14` — 14 atomic commits with clear messages
- [ ] Path traversal: `curl http://localhost:8000/../../etc/passwd` → serves index.html
- [ ] Auth: `curl http://localhost:8000/api/data/reports` → 401 (when key configured)
- [ ] Cooldown: rapid `POST /api/data/ingest` → 429 on second call
