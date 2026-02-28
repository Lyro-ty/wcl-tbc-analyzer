# Auto Speed Rankings Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically refresh speed rankings (top 100 fastest kills per encounter) before each weekly benchmark pipeline run, making the entire benchmark flow fully automated.

**Architecture:** Add a `_refresh_speed_rankings(wcl)` method to `AutoIngestService` that queries encounter IDs from the DB (filtered by `benchmark.zone_ids`), then calls the existing `ingest_all_speed_rankings()`. Called inside `_benchmark_loop()` before `run_benchmark_pipeline()`. Speed rankings errors are caught independently so benchmarks still run with stale data if the refresh fails.

**Tech Stack:** Python 3.12, SQLAlchemy async, existing `speed_rankings.py` pipeline module

---

### Task 1: Write failing tests for `_refresh_speed_rankings`

**Files:**
- Modify: `code/tests/pipeline/test_auto_ingest.py`

**Step 1: Write the failing tests**

Add to the end of the file, inside a new test class:

```python
class TestSpeedRankingsAutoRefresh:
    """Tests for automatic speed rankings refresh in benchmark loop."""

    @patch("shukketsu.pipeline.auto_ingest.ingest_all_speed_rankings")
    async def test_refresh_speed_rankings_calls_ingest(self, mock_ingest):
        """_refresh_speed_rankings queries encounters and calls ingest."""
        settings = _make_settings(benchmark_enabled=True)
        settings.benchmark.zone_ids = []

        mock_encounter = MagicMock()
        mock_encounter.id = 50649

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_encounter]
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_exec_result

        session_factory = _make_transactional_session_factory(mock_session)
        wcl = AsyncMock()
        mock_ingest.return_value = MagicMock(fetched=1, skipped=0, errors=[])

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._refresh_speed_rankings(wcl)

        mock_ingest.assert_called_once()
        call_args = mock_ingest.call_args
        assert call_args.args[0] is wcl  # wcl client
        assert call_args.args[2] == [50649]  # encounter_ids

    @patch("shukketsu.pipeline.auto_ingest.ingest_all_speed_rankings")
    async def test_refresh_speed_rankings_filters_by_zone_ids(self, mock_ingest):
        """When benchmark.zone_ids is set, encounters are filtered."""
        settings = _make_settings(benchmark_enabled=True)
        settings.benchmark.zone_ids = [1047, 1048]

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_exec_result

        session_factory = _make_transactional_session_factory(mock_session)
        wcl = AsyncMock()

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._refresh_speed_rankings(wcl)

        # With no encounters found, ingest should not be called
        mock_ingest.assert_not_called()

    @patch("shukketsu.pipeline.auto_ingest.ingest_all_speed_rankings")
    async def test_refresh_speed_rankings_skips_when_no_encounters(self, mock_ingest):
        """No encounters in DB -> skip without error."""
        settings = _make_settings(benchmark_enabled=True)
        settings.benchmark.zone_ids = []

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_exec_result

        session_factory = _make_transactional_session_factory(mock_session)
        wcl = AsyncMock()

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._refresh_speed_rankings(wcl)

        mock_ingest.assert_not_called()

    def test_status_includes_speed_rankings_run(self):
        """get_status() includes last_speed_rankings_run field."""
        settings = _make_settings(benchmark_enabled=True)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())
        status = svc.get_status()
        assert "last_speed_rankings_run" in status
        assert status["last_speed_rankings_run"] is None
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py::TestSpeedRankingsAutoRefresh -v`
Expected: FAIL — `_refresh_speed_rankings` method doesn't exist, `last_speed_rankings_run` not in status

---

### Task 2: Implement `_refresh_speed_rankings` method

**Files:**
- Modify: `code/shukketsu/pipeline/auto_ingest.py`

**Step 1: Add import and new method**

Add to the top imports (after existing `from sqlalchemy import select`):

```python
from shukketsu.db.models import Encounter
```

Add `_last_speed_rankings_run` to `__init__`:

```python
self._last_speed_rankings_run: datetime | None = None
```

Add the method to `AutoIngestService` (after `_benchmark_loop`, before `_poll_loop`):

```python
async def _refresh_speed_rankings(self, wcl) -> None:
    """Refresh speed rankings for all encounters in benchmark zones."""
    from shukketsu.pipeline.speed_rankings import ingest_all_speed_rankings

    zone_ids = self.settings.benchmark.zone_ids

    async with self._session_factory() as session:
        query = select(Encounter)
        if zone_ids:
            query = query.where(Encounter.zone_id.in_(zone_ids))
        result = await session.execute(query)
        encounter_ids = [e.id for e in result.scalars().all()]

    if not encounter_ids:
        logger.warning("No encounters found for speed rankings refresh")
        return

    logger.info(
        "Refreshing speed rankings for %d encounters",
        len(encounter_ids),
    )

    async with self._session_factory() as session:
        sr_result = await ingest_all_speed_rankings(
            wcl, session, encounter_ids,
        )
        logger.info(
            "Speed rankings refresh: fetched=%d, skipped=%d, errors=%d",
            sr_result.fetched, sr_result.skipped, len(sr_result.errors),
        )
    self._last_speed_rankings_run = datetime.now(UTC)
```

**Step 2: Add `last_speed_rankings_run` to `get_status()`**

In `get_status()`, add after `last_benchmark_run`:

```python
"last_speed_rankings_run": (
    self._last_speed_rankings_run.isoformat()
    if self._last_speed_rankings_run else None
),
```

**Step 3: Run tests to verify they pass**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py::TestSpeedRankingsAutoRefresh -v`
Expected: PASS

**Step 4: Commit**

```
feat: add _refresh_speed_rankings to AutoIngestService
```

---

### Task 3: Wire speed rankings refresh into `_benchmark_loop`

**Files:**
- Modify: `code/shukketsu/pipeline/auto_ingest.py`
- Modify: `code/tests/pipeline/test_auto_ingest.py`

**Step 1: Write failing test**

Add to `TestSpeedRankingsAutoRefresh`:

```python
def test_benchmark_loop_calls_refresh_speed_rankings(self):
    """_benchmark_loop must call _refresh_speed_rankings before benchmarks."""
    source = inspect.getsource(AutoIngestService._benchmark_loop)
    assert "_refresh_speed_rankings" in source
    # Speed rankings must come BEFORE run_benchmark_pipeline
    sr_pos = source.index("_refresh_speed_rankings")
    bp_pos = source.index("run_benchmark_pipeline")
    assert sr_pos < bp_pos

def test_benchmark_loop_catches_speed_rankings_error(self):
    """Speed rankings failure must not prevent benchmark pipeline."""
    source = inspect.getsource(AutoIngestService._benchmark_loop)
    # There should be a try/except around _refresh_speed_rankings
    # that's separate from the main try/except
    assert "Speed rankings refresh failed" in source
```

Add `import inspect` to the test file imports (already there).

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py::TestSpeedRankingsAutoRefresh::test_benchmark_loop_calls_refresh_speed_rankings -v`
Expected: FAIL — `_refresh_speed_rankings` not in `_benchmark_loop` source

**Step 3: Update `_benchmark_loop` to call speed rankings first**

Replace the entire `_benchmark_loop` method:

```python
async def _benchmark_loop(self) -> None:
    """Weekly benchmark refresh loop: speed rankings then benchmarks."""
    interval = self._benchmark_interval_days * 86400  # days to seconds
    while True:
        await asyncio.sleep(interval)
        try:
            from shukketsu.pipeline.benchmarks import run_benchmark_pipeline

            async with self._ingest_lock:
                async with self._wcl_factory() as wcl:
                    # Step 1: Refresh speed rankings
                    try:
                        await self._refresh_speed_rankings(wcl)
                    except Exception:
                        logger.exception(
                            "Speed rankings refresh failed,"
                            " continuing with benchmarks"
                        )

                    # Step 2: Run benchmark pipeline
                    async with self._session_factory() as session:
                        result = await run_benchmark_pipeline(
                            wcl, session,
                            max_reports_per_encounter=(
                                self._benchmark_max_reports
                            ),
                        )
                        logger.info(
                            "Benchmark auto-refresh: discovered=%d,"
                            " ingested=%d, computed=%d",
                            result.discovered, result.ingested,
                            result.computed,
                        )
            self._last_benchmark_run = datetime.now(UTC)
        except Exception:
            logger.exception("Benchmark auto-refresh failed")
```

**Step 4: Run all auto_ingest tests**

Run: `python3 -m pytest code/tests/pipeline/test_auto_ingest.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -v`
Expected: ALL PASS

**Step 6: Lint**

Run: `python3 -m ruff check code/shukketsu/pipeline/auto_ingest.py code/tests/pipeline/test_auto_ingest.py`
Expected: No errors

**Step 7: Commit**

```
feat: wire speed rankings auto-refresh into weekly benchmark loop
```
