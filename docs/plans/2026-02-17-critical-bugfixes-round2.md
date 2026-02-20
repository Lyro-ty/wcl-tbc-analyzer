# Critical Bugfixes Round 2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 12 issues identified in the senior-engineer code review: 3 critical, 4 high, 5 medium severity bugs spanning SQL logic, concurrency, transaction safety, error handling, and resilience.

**Architecture:** Targeted fixes to existing modules — no new files, no new dependencies. Each fix is isolated and independently testable. Tests first (TDD), then implementation.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, asyncio, pytest

---

## Task 1: Fix COMPARE_TWO_RAIDS SQL GROUP BY Bug (Critical)

**Files:**
- Modify: `code/shukketsu/db/queries.py:156-202`
- Test: `code/tests/integration/test_queries.py` (add case)
- Test: `code/tests/db/test_queries_logic.py` (new — unit test for SQL text correctness)

**Step 1: Write the failing test**

In `code/tests/db/test_queries_logic.py`:

```python
"""Unit tests that verify SQL query text correctness (not execution)."""

from shukketsu.db import queries as q


class TestCompareTwoRaidsQuery:
    def test_raid_a_groups_by_fight_id(self):
        """raid_a CTE must GROUP BY f.id to avoid merging duplicate boss kills."""
        sql = q.COMPARE_TWO_RAIDS.text
        # Find the raid_a CTE's GROUP BY clause
        raid_a_section = sql.split("raid_b AS")[0]
        group_by = raid_a_section.split("GROUP BY")[1].strip()
        assert "f.id" in group_by

    def test_raid_b_groups_by_fight_id(self):
        """raid_b CTE must GROUP BY f.id to avoid merging duplicate boss kills."""
        sql = q.COMPARE_TWO_RAIDS.text
        # Find the raid_b CTE's GROUP BY clause
        raid_b_section = sql.split("raid_b AS")[1].split("SELECT COALESCE")[0]
        group_by = raid_b_section.split("GROUP BY")[1].strip()
        assert "f.id" in group_by
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/db/test_queries_logic.py -v`
Expected: FAIL — `f.id` not in GROUP BY

**Step 3: Fix the SQL query**

In `code/shukketsu/db/queries.py`, change both CTEs:

```python
# Line 172: raid_a GROUP BY — add f.id
GROUP BY f.id, f.encounter_id, e.name, f.duration_ms, f.kill

# Line 189: raid_b GROUP BY — add f.id
GROUP BY f.id, f.encounter_id, e.name, f.duration_ms, f.kill
```

Also update the FULL OUTER JOIN to match on both encounter_id AND fight_id (since each CTE row now represents a single fight, the join should be on encounter_id to pair boss kills across raids):

The JOIN stays on `encounter_id` — this is correct. Multiple kills of the same boss in one raid will produce multiple rows per raid, paired by encounter.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/db/test_queries_logic.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -v --tb=short 2>&1 | tail -20`
Expected: All passing

**Step 6: Commit**

```
fix: add f.id to COMPARE_TWO_RAIDS GROUP BY to prevent fight merging
```

---

## Task 2: Add Semaphore to /analyze/stream Endpoint (Critical)

**Files:**
- Modify: `code/shukketsu/api/routes/analyze.py:97-159`
- Test: `code/tests/api/test_analyze.py` (add case)

**Step 1: Write the failing test**

In `code/tests/api/test_analyze.py`, add:

```python
class TestAnalyzeStreamSemaphore:
    async def test_stream_uses_semaphore(self):
        """Streaming endpoint must use the same LLM semaphore as /analyze."""
        from shukketsu.api.routes import analyze as mod

        # Verify the semaphore is acquired in event_generator
        # by checking it's referenced in the function
        import inspect
        source = inspect.getsource(mod.analyze_stream)
        assert "_llm_semaphore" in source
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/api/test_analyze.py::TestAnalyzeStreamSemaphore -v`
Expected: FAIL — `_llm_semaphore` not in `analyze_stream` source

**Step 3: Add semaphore to streaming endpoint**

In `code/shukketsu/api/routes/analyze.py`, wrap the event_generator's graph.astream call:

```python
@router.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest):
    graph = _get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def event_generator():
        buffer = ""
        think_done = False
        query_type = None

        try:
            config = {}
            handler = _get_langfuse_handler()
            if handler:
                config["callbacks"] = [handler]
            async with _llm_semaphore:
                async for chunk, metadata in graph.astream(
                    {"messages": [HumanMessage(content=request.question)]},
                    stream_mode="messages",
                    config=config,
                ):
                    # ... rest unchanged inside the loop ...
```

Move the closing logic (buffer flush, done event) INSIDE the `async with _llm_semaphore:` block so the semaphore is held for the entire stream duration.

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/api/test_analyze.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: add semaphore to /analyze/stream to cap concurrent LLM calls
```

---

## Task 3: Wrap Rankings Scripts in Transaction (Critical)

**Files:**
- Modify: `code/shukketsu/scripts/pull_rankings.py:128-140`
- Modify: `code/shukketsu/scripts/pull_speed_rankings.py:93-103`
- Test: `code/tests/scripts/test_pull_rankings_txn.py` (new)

**Step 1: Write the failing test**

In `code/tests/scripts/test_pull_rankings_txn.py`:

```python
"""Verify ranking scripts use explicit transactions."""

import inspect

from shukketsu.scripts import pull_rankings, pull_speed_rankings


class TestRankingsTransactions:
    def test_pull_rankings_uses_session_begin(self):
        """pull_rankings.run() must wrap session in begin() for atomicity."""
        source = inspect.getsource(pull_rankings.run)
        assert "session.begin()" in source

    def test_pull_speed_rankings_uses_session_begin(self):
        """pull_speed_rankings.run() must wrap session in begin() for atomicity."""
        source = inspect.getsource(pull_speed_rankings.run)
        assert "session.begin()" in source
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/scripts/test_pull_rankings_txn.py -v`
Expected: FAIL — `session.begin()` not in source

**Step 3: Add transaction wrapping**

In `code/shukketsu/scripts/pull_rankings.py`, change lines 128-140:

```python
    async with (
        WCLClient(auth, RateLimiter()) as wcl,
        session_factory() as session,
        session.begin(),
    ):
        result = await ingest_all_rankings(
            wcl,
            session,
            encounter_ids,
            specs,
            include_hps=include_hps,
            force=force,
            stale_hours=stale_hours,
        )
```

In `code/shukketsu/scripts/pull_speed_rankings.py`, change lines 93-103:

```python
    async with (
        WCLClient(auth, RateLimiter()) as wcl,
        session_factory() as session,
        session.begin(),
    ):
        result = await ingest_all_speed_rankings(
            wcl,
            session,
            encounter_ids,
            force=force,
            stale_hours=stale_hours,
        )
```

Note: `ingest_all_rankings` and `ingest_all_speed_rankings` both call `session.commit()` internally per encounter batch. Under `session.begin()`, these commits will commit the outer transaction and implicitly start a new one (SQLAlchemy autobegin). This is fine — the key improvement is that the initial delete-then-insert within `fetch_rankings_for_spec` / `fetch_speed_rankings_for_encounter` is now inside a transaction.

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/scripts/test_pull_rankings_txn.py -v`
Expected: PASS

**Step 5: Run full suite**

Run: `python3 -m pytest code/tests/ -v --tb=short 2>&1 | tail -20`
Expected: All passing

**Step 6: Commit**

```
fix: wrap rankings scripts in explicit transactions to prevent data loss
```

---

## Task 4: Cap Rate Limiter Sleep Duration (High)

**Files:**
- Modify: `code/shukketsu/wcl/rate_limiter.py:37-45`
- Test: `code/tests/wcl/test_rate_limiter.py` (add cases)

**Step 1: Write the failing test**

In `code/tests/wcl/test_rate_limiter.py`, add:

```python
class TestRateLimiterSleepCap:
    async def test_sleep_capped_at_one_hour(self):
        """Sleep duration must be capped even if WCL returns bogus pointsResetIn."""
        rl = RateLimiter()
        rl.update({
            "pointsSpentThisHour": 3500,
            "limitPerHour": 3600,
            "pointsResetIn": 86400,  # 24 hours — bogus
        })
        assert rl._points_reset_in == 86400  # stored as-is
        # But the actual sleep should be capped
        # We test this by checking MAX_SLEEP_SECONDS exists and is used
        assert hasattr(RateLimiter, 'MAX_SLEEP_SECONDS')
        assert RateLimiter.MAX_SLEEP_SECONDS == 3600

    async def test_wait_sleeps_capped_duration(self, monkeypatch):
        """wait_if_needed() should sleep min(pointsResetIn, MAX_SLEEP_SECONDS)."""
        import asyncio
        slept = []
        monkeypatch.setattr(asyncio, "sleep", lambda s: slept.append(s) or asyncio.coroutine(lambda: None)())

        rl = RateLimiter()
        rl.update({
            "pointsSpentThisHour": 3500,
            "limitPerHour": 3600,
            "pointsResetIn": 7200,
        })
        await rl.wait_if_needed()
        assert slept[0] == 3600  # capped, not 7200
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/wcl/test_rate_limiter.py::TestRateLimiterSleepCap -v`
Expected: FAIL — no `MAX_SLEEP_SECONDS` attribute

**Step 3: Add the cap**

In `code/shukketsu/wcl/rate_limiter.py`:

```python
class RateLimiter:
    MAX_SLEEP_SECONDS: int = 3600

    # ... existing __init__ and methods ...

    async def wait_if_needed(self) -> None:
        if not self.is_safe:
            sleep_duration = min(self._points_reset_in, self.MAX_SLEEP_SECONDS)
            logger.warning(
                "Rate limit near threshold (%d/%d), sleeping %ds (raw reset_in=%ds)",
                self._points_spent,
                self.limit_per_hour,
                sleep_duration,
                self._points_reset_in,
            )
            await asyncio.sleep(sleep_duration)
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/wcl/test_rate_limiter.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: cap rate limiter sleep at 1 hour to prevent indefinite blocking
```

---

## Task 5: Cancel Trigger Task on Auto-Ingest Shutdown + Add Backoff (High)

**Files:**
- Modify: `code/shukketsu/pipeline/auto_ingest.py:48-70`
- Test: `code/tests/pipeline/test_auto_ingest.py` (add cases)

**Step 1: Write the failing tests**

Add to `code/tests/pipeline/test_auto_ingest.py`:

```python
class TestAutoIngestShutdown:
    async def test_stop_cancels_trigger_task(self):
        """stop() must cancel _trigger_task if one is running."""
        import inspect
        from shukketsu.pipeline.auto_ingest import AutoIngestService
        source = inspect.getsource(AutoIngestService.stop)
        assert "_trigger_task" in source

class TestAutoIngestBackoff:
    async def test_poll_loop_uses_backoff_on_errors(self):
        """Poll loop should increase sleep duration after consecutive errors."""
        import inspect
        from shukketsu.pipeline.auto_ingest import AutoIngestService
        source = inspect.getsource(AutoIngestService._poll_loop)
        assert "consecutive_errors" in source or "_consecutive_errors" in source
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py::TestAutoIngestShutdown -v`
Expected: FAIL

**Step 3: Fix auto_ingest.py**

In `code/shukketsu/pipeline/auto_ingest.py`:

Add to `__init__`:
```python
self._consecutive_errors: int = 0
```

Fix `stop()`:
```python
async def stop(self):
    """Stop the background polling loop."""
    if self._trigger_task and not self._trigger_task.done():
        self._trigger_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._trigger_task
    if self._task and not self._task.done():
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
    self._status = "idle"
    logger.info("Auto-ingest stopped")
```

Fix `_poll_loop()` with exponential backoff:
```python
async def _poll_loop(self):
    """Main polling loop with exponential backoff on errors."""
    base_interval = self.settings.auto_ingest.poll_interval_minutes * 60
    max_backoff = base_interval * 8  # cap at 8x normal interval
    while True:
        try:
            await self._poll_once()
            self._consecutive_errors = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Error in auto-ingest poll loop")
            self._status = "error"
            self._last_error = str(exc)
            self._stats["errors"] += 1
            self._consecutive_errors += 1

        if self._consecutive_errors > 0:
            backoff = min(
                base_interval * (2 ** self._consecutive_errors),
                max_backoff,
            )
            logger.warning(
                "Auto-ingest backing off: %ds (consecutive errors: %d)",
                backoff, self._consecutive_errors,
            )
            await asyncio.sleep(backoff)
        else:
            await asyncio.sleep(base_interval)
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: cancel trigger task on shutdown, add exponential backoff on errors
```

---

## Task 6: Add Statement Timeout to DB Engine (High)

**Files:**
- Modify: `code/shukketsu/db/engine.py`
- Modify: `code/shukketsu/config.py` (add `statement_timeout_ms` field)
- Test: `code/tests/db/test_engine.py` (new)

**Step 1: Write the failing test**

In `code/tests/db/test_engine.py`:

```python
"""Verify DB engine configuration."""

from unittest.mock import patch

from shukketsu.config import Settings
from shukketsu.db.engine import create_db_engine


class TestDbEngine:
    def test_engine_sets_statement_timeout(self):
        """Engine must configure PostgreSQL statement_timeout via connect_args."""
        settings = Settings()
        with patch(
            "shukketsu.db.engine.create_async_engine"
        ) as mock_create:
            create_db_engine(settings)
            call_kwargs = mock_create.call_args[1]
            server_settings = call_kwargs["connect_args"]["server_settings"]
            assert "statement_timeout" in server_settings
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/db/test_engine.py -v`
Expected: FAIL — no `connect_args` in engine

**Step 3: Add statement_timeout**

In `code/shukketsu/config.py`, add to `DbSettings`:
```python
statement_timeout_ms: int = 30000  # 30 seconds
```

In `code/shukketsu/db/engine.py`:
```python
def create_db_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.db.url,
        echo=settings.db.echo,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "statement_timeout": str(settings.db.statement_timeout_ms),
            },
        },
    )
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/db/test_engine.py -v`
Expected: PASS

**Step 5: Run full suite**

Run: `python3 -m pytest code/tests/ -v --tb=short 2>&1 | tail -20`
Expected: All passing

**Step 6: Commit**

```
fix: add PostgreSQL statement_timeout to prevent runaway queries
```

---

## Task 7: Fix Cooldown Race Condition (Medium)

**Files:**
- Modify: `code/shukketsu/api/deps.py:17-75`
- Test: `code/tests/api/test_deps.py` (add case)

**Step 1: Write the failing test**

In `code/tests/api/test_deps.py` (create if needed):

```python
"""Tests for FastAPI dependency providers."""

import asyncio

from shukketsu.api.deps import cooldown, _cooldowns


class TestCooldownRaceCondition:
    async def test_concurrent_requests_one_passes_cooldown(self):
        """Only one of two concurrent requests should pass the cooldown check."""
        _cooldowns.clear()

        check = cooldown("test_race", seconds=60)
        # Extract the inner _check_cooldown function
        dep_fn = check.dependency

        passed = 0
        failed = 0

        async def try_cooldown():
            nonlocal passed, failed
            try:
                await dep_fn()
                passed += 1
            except Exception:
                failed += 1

        await asyncio.gather(try_cooldown(), try_cooldown())
        # With proper locking, exactly one should pass
        assert passed == 1
        assert failed == 1
        _cooldowns.clear()
```

**Step 2: Run test to verify it fails (flaky — may pass sometimes)**

Run: `python3 -m pytest code/tests/api/test_deps.py::TestCooldownRaceCondition -v`
Expected: May FAIL (both pass) due to race condition

**Step 3: Add asyncio.Lock to cooldown**

In `code/shukketsu/api/deps.py`:

```python
import asyncio

# Cooldown tracking for WCL-calling endpoints
_cooldowns: dict[str, float] = {}
_cooldown_lock = asyncio.Lock()


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
                    detail=f"Please wait {int(remaining)}s before retrying",
                )
            _cooldowns[key] = now

    return Depends(_check_cooldown)
```

**Step 4: Run test**

Run: `python3 -m pytest code/tests/api/test_deps.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: add asyncio lock to cooldown to prevent race condition bypass
```

---

## Task 8: Sanitize Tool Error Messages (Medium)

**Files:**
- Modify: `code/shukketsu/agent/tool_utils.py:54-58`
- Test: `code/tests/agent/test_tool_utils.py` (add case)

**Step 1: Write the failing test**

In `code/tests/agent/test_tool_utils.py` (create if needed):

```python
"""Tests for tool_utils module."""

from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.agent.tool_utils import db_tool


class TestDbToolErrorSanitization:
    async def test_error_message_does_not_leak_sql(self):
        """Tool errors must not include raw SQL or connection details."""
        @db_tool
        async def bad_tool(session, name: str) -> str:
            raise Exception(
                '(sqlalchemy.exc.ProgrammingError) relation "secret_table" '
                'at postgresql://user:pass@host:5432/db'
            )

        mock_session = AsyncMock()
        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await bad_tool.ainvoke({"name": "test"})

        assert "postgresql://" not in result
        assert "pass@" not in result
        assert "Error" in result
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/agent/test_tool_utils.py::TestDbToolErrorSanitization -v`
Expected: FAIL — raw exception string leaks through

**Step 3: Sanitize error messages**

In `code/shukketsu/agent/tool_utils.py`, change the except block:

```python
        except Exception as e:
            logger.exception("Tool error in %s", fn.__name__)
            # Sanitize: don't leak SQL, connection strings, or internals to LLM
            error_type = type(e).__name__
            return f"Error retrieving data: {error_type} in {fn.__name__}. Please try a different query."
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/agent/test_tool_utils.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: sanitize tool error messages to prevent leaking internals to LLM
```

---

## Task 9: Handle Client Disconnects in SSE Stream (Medium)

**Files:**
- Modify: `code/shukketsu/api/routes/analyze.py:97-159`
- Test: `code/tests/api/test_analyze.py` (add case)

**Step 1: Write the test**

In `code/tests/api/test_analyze.py`, add:

```python
class TestStreamingBufferLimit:
    def test_think_buffer_has_max_size(self):
        """Streaming think-tag buffer must have a maximum size to prevent OOM."""
        import inspect
        from shukketsu.api.routes import analyze as mod
        source = inspect.getsource(mod.analyze_stream)
        # Buffer must be bounded
        assert "MAX_THINK_BUFFER" in source or "max_buffer" in source or "len(buffer)" in source
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/api/test_analyze.py::TestStreamingBufferLimit -v`
Expected: FAIL

**Step 3: Add buffer limit and CancelledError handling**

In `code/shukketsu/api/routes/analyze.py`:

Add constant:
```python
_MAX_THINK_BUFFER = 32768  # 32KB max for think-tag buffering
```

Update event_generator:
```python
    async def event_generator():
        buffer = ""
        think_done = False
        query_type = None

        try:
            config = {}
            handler = _get_langfuse_handler()
            if handler:
                config["callbacks"] = [handler]
            async with _llm_semaphore:
                async for chunk, metadata in graph.astream(
                    {"messages": [HumanMessage(content=request.question)]},
                    stream_mode="messages",
                    config=config,
                ):
                    if isinstance(metadata, dict):
                        qt = metadata.get("query_type")
                        if qt:
                            query_type = qt

                    if not isinstance(metadata, dict):
                        continue
                    if metadata.get("langgraph_node") != "analyze":
                        continue

                    if not hasattr(chunk, "content") or not chunk.content:
                        continue

                    token = chunk.content

                    if not think_done:
                        buffer += token
                        # Safety: if buffer exceeds limit, flush and skip think stripping
                        if len(buffer) > _MAX_THINK_BUFFER:
                            cleaned = _strip_think_tags(buffer)
                            if cleaned.strip():
                                yield {"data": json.dumps({"token": cleaned})}
                            buffer = ""
                            think_done = True
                            continue
                        if "</think>" in buffer:
                            after = _THINK_PATTERN.sub("", buffer)
                            think_done = True
                            buffer = ""
                            if after.strip():
                                yield {"data": json.dumps({"token": after})}
                        continue

                    yield {"data": json.dumps({"token": token})}

                if buffer and not think_done:
                    cleaned = _strip_think_tags(buffer)
                    if cleaned.strip():
                        yield {"data": json.dumps({"token": cleaned})}

                yield {"data": json.dumps({"done": True, "query_type": query_type})}

        except asyncio.CancelledError:
            logger.info("Streaming analysis cancelled (client disconnect)")
            return
        except Exception:
            logger.exception("Streaming analysis failed")
            yield {"event": "error", "data": json.dumps({"detail": "Analysis failed"})}
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/api/test_analyze.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: add buffer limit and client disconnect handling to SSE stream
```

---

## Task 10: Surface Enrichment Errors in Ingest Result (Medium)

**Files:**
- Modify: `code/shukketsu/pipeline/ingest.py:274-280`
- Test: `code/tests/pipeline/test_ingest.py` (add case)

The ingest pipeline already tracks enrichment errors in the `enrichment_errors` list and returns them in `IngestResult`. The `enrichment_errors` field is populated and logged at line 274-279. This is actually handled — the caller (auto_ingest and scripts) just doesn't surface it.

**Step 1: Write the test**

In `code/tests/pipeline/test_ingest.py`, add:

```python
class TestEnrichmentErrorTracking:
    def test_ingest_result_includes_enrichment_errors(self):
        """IngestResult must expose enrichment_errors list."""
        from shukketsu.pipeline.ingest import IngestResult
        result = IngestResult(fights=5, performances=50)
        result.enrichment_errors.append("table_data_fight_1")
        assert len(result.enrichment_errors) == 1
        assert result.enrichment_errors[0] == "table_data_fight_1"
```

This test should pass already. The real fix is making the auto-ingest log the enrichment errors:

**Step 2: Fix auto_ingest to log enrichment warnings**

In `code/shukketsu/pipeline/auto_ingest.py`, after `await ingest_report(...)`, the result is not captured. Change:

```python
                        result = await ingest_report(
                            wcl, session, code,
                            my_character_names=my_names,
                            ingest_tables=cfg.with_tables,
                            ingest_events=cfg.with_events,
                        )
                    if result.enrichment_errors:
                        logger.warning(
                            "Enrichment errors for %s: %s",
                            code, result.enrichment_errors,
                        )
```

**Step 3: Run tests**

Run: `python3 -m pytest code/tests/pipeline/test_ingest.py -v`
Expected: PASS

**Step 4: Commit**

```
fix: log enrichment errors in auto-ingest for observability
```

---

## Task 11: Use Async Context Manager for Health Check Session (Medium)

**Files:**
- Modify: `code/shukketsu/api/routes/health.py:28-38`
- Test: `code/tests/api/test_health.py` (verify existing tests still pass)

**Step 1: Write the test**

```python
class TestHealthSessionManagement:
    def test_health_uses_async_context_manager(self):
        """Health check must use 'async with' for session to guarantee cleanup."""
        import inspect
        from shukketsu.api.routes import health
        source = inspect.getsource(health.health)
        assert "async with" in source
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/api/test_health.py::TestHealthSessionManagement -v`
Expected: FAIL — uses manual try/finally, not `async with`

**Step 3: Fix health check**

In `code/shukketsu/api/routes/health.py`:

```python
    # Check database
    if _session_factory:
        try:
            async with _session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception as e:
            logger.warning("Health check: DB unreachable: %s", e)
            db_status = "error"
            healthy = False
    else:
        db_status = "not configured"
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/api/test_health.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: use async context manager for health check DB session
```

---

## Task 12: Fix GEAR_CHANGES Query to Use Stable Ordering (Low)

**Files:**
- Modify: `code/shukketsu/db/queries.py:688-709`
- Test: `code/tests/db/test_queries_logic.py` (add case)

**Step 1: Write the failing test**

In `code/tests/db/test_queries_logic.py`, add:

```python
class TestGearChangesQuery:
    def test_uses_min_id_not_min_fight_id(self):
        """GEAR_CHANGES should use MIN(f.id) not MIN(f.fight_id) for stable ordering."""
        sql = q.GEAR_CHANGES.text
        # Should use the stable auto-increment PK, not WCL's fight_id
        assert "MIN(f2.id)" in sql
        assert "MIN(f2.fight_id)" not in sql
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/db/test_queries_logic.py::TestGearChangesQuery -v`
Expected: FAIL

**Step 3: Fix the query**

In `code/shukketsu/db/queries.py`, change both subqueries in GEAR_CHANGES:

```sql
AND f.id = (
    SELECT MIN(f2.id) FROM fights f2
    WHERE f2.report_code = :report_code_old
)
```
and
```sql
AND f.id = (
    SELECT MIN(f2.id) FROM fights f2
    WHERE f2.report_code = :report_code_new
)
```

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/db/test_queries_logic.py -v`
Expected: PASS

**Step 5: Commit**

```
fix: use MIN(f.id) in GEAR_CHANGES for stable fight ordering
```

---

## Task 13: Run Full Test Suite + Lint (Verification)

**Step 1: Run full test suite**

Run: `python3 -m pytest code/tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests passing

**Step 2: Run linter**

Run: `python3 -m ruff check code/`
Expected: No errors

**Step 3: Final commit (if any lint fixes needed)**

```
chore: lint fixes
```

---

## Summary

| Task | Severity | Issue | Fix |
|------|----------|-------|-----|
| 1 | Critical | COMPARE_TWO_RAIDS merges fights | Add f.id to GROUP BY |
| 2 | Critical | /analyze/stream unlimited concurrency | Add semaphore |
| 3 | Critical | Rankings scripts no transaction | Wrap in session.begin() |
| 4 | High | Rate limiter sleeps forever | Cap at 3600s |
| 5 | High | Auto-ingest trigger not cancelled, no backoff | Fix stop(), add backoff |
| 6 | High | No DB query timeout | Add statement_timeout |
| 7 | Medium | Cooldown race condition | Add asyncio.Lock |
| 8 | Medium | Tool errors leak internals | Sanitize error messages |
| 9 | Medium | SSE buffer unbounded, no disconnect handling | Add limit + CancelledError |
| 10 | Medium | Enrichment errors silent in auto-ingest | Log warnings |
| 11 | Medium | Health check session cleanup | Use async with |
| 12 | Low | GEAR_CHANGES uses unstable fight_id ordering | Use MIN(f.id) |
| 13 | — | Verification | Full suite + lint |
