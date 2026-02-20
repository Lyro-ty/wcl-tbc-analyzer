# Fix Plan: 18 Security, Integrity & Architecture Issues

**Date:** 2026-02-17
**Scope:** 18 issues across security, data integrity, resilience, architecture, and testing
**Deployment context:** Local/LAN only — simplified auth and cooldown guards

---

## Phase 1 — Critical Quick Wins

Surgical, zero-dependency fixes. Each is independently testable.

### Issue 1: Path traversal in SPA catchall [CRITICAL, 5 min]

**File:** `code/shukketsu/api/app.py` (lines 137-143)

**Problem:** The `/{path:path}` catchall concatenates user input directly into a filesystem path. `GET /../../../../etc/passwd` reads arbitrary files.

**Fix:** Resolve the path and validate it stays within `FRONTEND_DIST`:

```python
@app.get("/{path:path}")
async def spa_catchall(path: str):
    resolved = (FRONTEND_DIST / path).resolve()
    if resolved.is_relative_to(FRONTEND_DIST.resolve()) and resolved.is_file():
        return FileResponse(resolved)
    return FileResponse(FRONTEND_DIST / "index.html")
```

**Tests:** Add `test_spa_path_traversal_blocked` in `tests/api/test_health.py`.

---

### Issue 3: CORS wildcard with credentials [CRITICAL, 1 min]

**File:** `code/shukketsu/api/app.py` (lines 115-121)

**Problem:** `allow_origins=["*"]` + `allow_credentials=True` is a spec violation (browsers reject it) and insecure.

**Fix:** Lock to local origins, disable credentials:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)
```

---

### Issue 6: Missing pool_pre_ping [HIGH, 2 min]

**File:** `code/shukketsu/db/engine.py` (lines 14-20)

**Problem:** Stale DB connections cause errors instead of silent reconnection.

**Fix:** Add `pool_pre_ping=True` to `create_async_engine()`.

---

### Issue 17: Auto-ingest concurrent task guard [MEDIUM, 15 min]

**File:** `code/shukketsu/pipeline/auto_ingest.py` (lines 166-169)

**Problem:** Rapid calls to `trigger_now()` spawn multiple concurrent `_poll_once()` tasks — race condition on DB session, duplicate ingests.

**Fix:** Guard like `start()` already does:

```python
async def trigger_now(self) -> dict:
    if self._trigger_task and not self._trigger_task.done():
        return {"status": "already_running", "message": "Poll already in progress"}
    self._trigger_task = asyncio.create_task(self._poll_once())
    return {"status": "triggered", "message": "Poll started in background"}
```

**Tests:** Add `test_trigger_now_rejects_concurrent` in `tests/pipeline/test_auto_ingest.py`.

---

## Phase 2 — Data Integrity & Resilience

DB schema fixes, transaction safety, pipeline error handling, and query bounds.

### Issues 12, 15, 18: Alembic migration for CASCADEs + CHECKs [MEDIUM, 30 min]

**File:** New `alembic/versions/004_add_cascades_and_checks.py`

**Single migration that:**

1. **CASCADE DELETE on all child FKs** (Issue 12 + 18):
   - `fights.report_code` → `reports.code` ON DELETE CASCADE
   - `fights.encounter_id` → `encounters.id` ON DELETE CASCADE
   - `fight_performances.fight_id` → `fights.id` ON DELETE CASCADE
   - All table-data FKs: `ability_metrics`, `buff_uptimes` → `fights.id` CASCADE
   - All event-data FKs: `death_details`, `cast_events`, `cast_metrics`, `cooldown_usage`, `cancelled_casts`, `resource_snapshots`, `fight_consumables`, `gear_snapshots` → `fights.id` CASCADE
   - `top_rankings.encounter_id` → `encounters.id` CASCADE
   - `speed_rankings.encounter_id` → `encounters.id` CASCADE

2. **CHECK constraints on bounded numeric fields** (Issue 15):
   - `fight_performances`: `parse_percentile BETWEEN 0 AND 100`, `dps >= 0`
   - `cast_metrics`: `gcd_uptime_pct BETWEEN 0 AND 100`
   - `buff_uptimes`: `uptime_pct BETWEEN 0 AND 100`
   - `cooldown_usage`: `efficiency_pct BETWEEN 0 AND 100`
   - `cancelled_casts`: `cancel_rate BETWEEN 0 AND 100`

3. **ORM model updates** to match: add `ondelete="CASCADE"` on `ForeignKey()` declarations, add `CheckConstraint` to `__table_args__`.

---

### Issue 4: Transaction boundaries in ingest [CRITICAL, 30 min]

**Files:** `code/shukketsu/pipeline/ingest.py`, CLI scripts, auto_ingest.py

**Problem:** `ingest_report()` has no explicit transaction control. Failures mid-ingest leave partial data (some fights ingested, others not).

**Design:**

1. `ingest_report()` becomes a pure function that writes to the session but **never commits** — caller owns the transaction:

```python
async def ingest_report(wcl, session, report_code, *, with_tables=False, with_events=False):
    # Phase 1: fetch from WCL (no DB writes)
    report_data = await wcl.query(...)
    fights_data = normalize_fights(report_data)

    # Phase 2: all core DB writes
    await _delete_existing_fights(session, report_code)
    session.merge(report_row)
    for fight in fights_data:
        session.add(fight_row)
    await session.flush()  # surface constraint violations

    # Phase 3: optional enrichment (tracked, not swallowed)
    enrichment_errors = []
    if with_tables:
        try:
            await ingest_table_data_for_report(wcl, session, report_code)
        except Exception as e:
            logger.error("Table data enrichment failed for %s: %s", report_code, e)
            enrichment_errors.append("table_data")
    if with_events:
        try:
            await ingest_events_for_report(wcl, session, report_code)
        except Exception as e:
            logger.error("Event enrichment failed for %s: %s", report_code, e)
            enrichment_errors.append("events")

    return IngestResult(report_code=report_code, enrichment_errors=enrichment_errors)
```

2. Callers use `session.begin()` for atomic transactions:

```python
# CLI scripts + auto-ingest:
async with session.begin():
    result = await ingest_report(wcl, session, report_code, ...)
# commit on success, rollback on exception — automatic
```

3. Progression snapshots run in a **separate transaction** after the ingest commit succeeds.

---

### Issue 5: Silent exception swallowing in pipeline [CRITICAL, 30 min]

**Files:** 9 pipeline modules with bare/broad `except Exception` blocks

**Problem:** Exceptions caught and silently continued — data is incomplete with no visibility.

**Design:**

- **Core pipeline functions** (fight normalization, performance parsing): remove try/except entirely — let exceptions propagate to the transaction boundary and trigger rollback.
- **Enrichment steps** (table data, events, combatant info): keep try/except but return structured error info via `IngestResult.enrichment_errors` (see Issue 4 above). Every caught exception gets `logger.error()` with context.
- **Audit all 9 modules** and categorize each except block as "must propagate" or "enrichment — log and track".

Affected modules:
- `ingest.py` — 3 except blocks
- `table_data.py` — 1 except block (no logging)
- `death_events.py` — 1 except block (no logging)
- `combatant_info.py` — 1 except block (no logging)
- `cast_events.py` — 1 except block (no logging)
- `resource_events.py` — 1 except block (no logging)
- `rankings.py` — 1 except block
- `speed_rankings.py` — 1 except block
- `auto_ingest.py` — 2 except blocks (already logged)

---

### Issue 9: Unbounded fetch_all_events() memory [HIGH, 1 hr]

**File:** `code/shukketsu/wcl/events.py` (lines 12-67)

**Problem:** Accumulates all event pages into a single list before returning. Large fights can produce thousands of events.

**Fix:** Convert to async generator yielding per-page:

```python
async def fetch_all_events(wcl, report_code, start_time, end_time, data_type, source_id=None):
    current_start = start_time
    while True:
        events_data = await _fetch_events_page(...)
        page_events = events_data.get("data", [])
        if page_events:
            yield page_events
        next_page = events_data.get("nextPageTimestamp")
        if next_page is None:
            break
        current_start = next_page
```

Callers change from `all_events = await fetch_all_events(...)` to `async for page in fetch_all_events(...)`. Memory drops from O(all events) to O(one page ~300 events).

**Affected callers:** `cast_events.py`, `death_events.py`, `resource_events.py` — each gets the same `async for page` pattern with `session.flush()` per page.

---

### Issue 13: Unbounded queries [MEDIUM, 30 min]

**File:** `code/shukketsu/db/queries.py`

Add LIMIT defaults to queries currently missing them:

| Query | Fix |
|-------|-----|
| `FIGHT_DETAILS` | `LIMIT 50` (max raid = 40 players) |
| `PROGRESSION` | `LIMIT 100` (~2 years of snapshots) |
| `SPEC_LEADERBOARD` | `LIMIT 50` |
| `RAID_EXECUTION` | `LIMIT 25` (max bosses per raid) |

Queries with existing limits or natural bounds (aggregates, single-row) unchanged.

---

## Phase 3 — Architecture Refactor

Split god modules, add `@db_tool` decorator, introduce FastAPI DI. Strict ordering: decorator → tools split → data split + DI.

### Issue 16: @db_tool decorator [MEDIUM, 1 hr]

**File:** New `code/shukketsu/agent/tool_utils.py`

Extracts the repeated session lifecycle + error handling into a decorator:

```python
def db_tool(fn):
    @tool
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        session = await _get_session()
        try:
            return await fn(session, *args, **kwargs)
        except Exception as e:
            return f"Error retrieving data: {e}"
        finally:
            await session.close()
    return wrapper
```

Each tool drops from ~25 lines to ~10 (pure query + format logic). Eliminates ~330 lines of duplicated boilerplate.

Also contains `_get_session()` and `set_session_factory()` — moved from tools.py.

---

### Issue 7a: Split tools.py [HIGH, 1-2 hr]

**From:** `code/shukketsu/agent/tools.py` (1,645 LOC)
**To:**

```
code/shukketsu/agent/
├── tool_utils.py              # @db_tool, session factory (~40 LOC)
├── tools/
│   ├── __init__.py            # ALL_TOOLS list, re-exports (~30 LOC)
│   ├── player_tools.py        # 11 tools (~400 LOC)
│   ├── raid_tools.py          # 3 tools (~120 LOC)
│   ├── table_tools.py         # 4 tools (~160 LOC)
│   └── event_tools.py         # 12 tools (~500 LOC)
```

`__init__.py` exports `ALL_TOOLS` list. `graph.py` changes one import line. All existing tool tests continue working since tool function names/signatures are unchanged.

---

### Issue 7b: Split data.py [HIGH, 1-2 hr]

**From:** `code/shukketsu/api/routes/data.py` (1,857 LOC)
**To:**

```
code/shukketsu/api/routes/
├── data/
│   ├── __init__.py            # creates router, includes sub-routers (~20 LOC)
│   ├── reports.py             # /api/reports, /api/ingest (~250 LOC)
│   ├── fights.py              # fight details, deaths, search (~300 LOC)
│   ├── characters.py          # roster, progression (~200 LOC)
│   ├── rankings.py            # rankings, speed rankings, leaderboard (~300 LOC)
│   ├── comparison.py          # raid comparison endpoints (~350 LOC)
│   └── events.py              # event-data endpoints (~350 LOC)
```

`app.py` changes one router include. All endpoint paths unchanged.

---

### Issue 8: Replace module globals with FastAPI DI [HIGH, 2 hr]

**Files:** `code/shukketsu/api/deps.py`, `app.py`, all route modules

**Design:**

`deps.py` becomes the DI hub (currently empty):

```python
_session_factory = None
_graph = None

def set_dependencies(session_factory, graph):
    global _session_factory, _graph
    _session_factory = session_factory
    _graph = graph

async def get_db() -> AsyncSession:
    if _session_factory is None:
        raise RuntimeError("DB not initialized")
    async with _session_factory() as session:
        yield session

def get_graph():
    if _graph is None:
        raise RuntimeError("Agent graph not initialized")
    return _graph
```

Route handlers use `Depends(get_db)` instead of manual session management. Sessions auto-close via the `async with` in `get_db()`.

**Scope boundary:** Agent tools keep their module-global pattern in `tool_utils.py`. LangChain `@tool` functions don't participate in FastAPI's request lifecycle — `Depends()` doesn't apply to them.

`app.py` lifespan calls both:
- `deps.set_dependencies(factory, graph)` for routes
- `tool_utils.set_session_factory(factory)` for agent tools

---

## Phase 4 — Auth, Cooldown Guards & Testing

Builds on Phase 3's DI for clean test fixtures and auth injection.

### Issue 2: API key auth [CRITICAL, 30 min]

**Files:** `config.py`, `deps.py`, `app.py`

**Design:** Single API key from `.env`, checked via FastAPI dependency.

1. Add `api_key: str = ""` to `AppSettings` in config.py
2. Add `verify_api_key` dependency in deps.py:
   - Reads `X-API-Key` header or `?api_key=` query param
   - If `APP__API_KEY` is empty → auth disabled (dev convenience)
   - If configured but missing/wrong → 401
3. Apply at router level in app.py:
   - Protected: data, analyze, auto-ingest routers
   - Unprotected: `/health`, SPA catchall

---

### Issue 14: Cooldown guards on WCL-calling endpoints [MEDIUM, 30 min]

**File:** `deps.py`

**Design:** Simple timestamp-based cooldown — no external dependencies:

```python
_cooldowns: dict[str, float] = {}

def cooldown(key: str, seconds: int = 300):
    async def check():
        now = time.monotonic()
        last = _cooldowns.get(key, 0)
        remaining = seconds - (now - last)
        if remaining > 0:
            raise HTTPException(429, f"Please wait {int(remaining)}s before retrying")
        _cooldowns[key] = now
    return Depends(check)
```

Applied to 4 endpoints:
- `POST /api/ingest` — 120s cooldown
- `POST /api/rankings/refresh` — 300s cooldown
- `POST /api/speed-rankings/refresh` — 300s cooldown
- `POST /api/auto-ingest/trigger` — 120s cooldown

---

### Issue 10: Route tests for data.py endpoints [HIGH, 3-4 hr]

**Directory:** `code/tests/api/`

**Test infrastructure** (shared conftest.py):

```python
@pytest.fixture
async def client(mock_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[verify_api_key] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

**New test files** mirroring the route split:

| File | Endpoints | Est. tests |
|------|-----------|------------|
| `test_reports.py` | list, get, ingest | ~10 |
| `test_fights.py` | fight details, deaths, search | ~12 |
| `test_characters.py` | roster, progression | ~8 |
| `test_rankings.py` | rankings, speed rankings, leaderboard | ~12 |
| `test_comparison.py` | raid comparisons | ~10 |
| `test_events.py` | cast-timeline, cooldowns, resources, etc. | ~15 |
| `test_auth.py` | API key acceptance/rejection | ~8 |

Coverage per endpoint:
- Happy path (200 + response shape)
- 404 for missing resources
- 401 when API key configured but missing
- 429 on cooldown-protected endpoints

Estimated: **~80-100 new tests**.

---

### Issue 11: Integration tests with Docker testcontainers [HIGH, 2-3 hr]

**Directory:** `code/tests/integration/`

**Infrastructure** (conftest.py):
- `testcontainers.postgres` spins up PostgreSQL 16 per test session
- Alembic migrations run against the test DB
- Each test gets a session wrapped in a rolled-back transaction (clean slate)

**Pytest marker:** `@pytest.mark.integration` — run separately via `pytest -m integration`

**Test files:**

| File | Validates | Est. tests |
|------|-----------|------------|
| `test_ingest_roundtrip.py` | Full ingest → query cycle | ~5 |
| `test_cascade_deletes.py` | Delete report → children cascade | ~5 |
| `test_constraints.py` | CHECK constraints reject bad data | ~8 |
| `test_queries.py` | All raw SQL queries execute without syntax errors | ~10 |
| `test_ilike.py` | Case-insensitive player matching works | ~3 |

Estimated: **~25-30 integration tests**.

**Run command:** `pytest code/tests/integration/ -v -m integration` (requires Docker)

---

## Commit Strategy

Each phase is a series of atomic commits:

| Commit | Phase | Scope |
|--------|-------|-------|
| 1 | P1 | fix: path traversal in SPA catchall |
| 2 | P1 | fix: CORS config, pool_pre_ping, auto-ingest guard |
| 3 | P2 | feat: alembic migration for CASCADE DELETE + CHECK constraints |
| 4 | P2 | feat: update ORM models to match migration |
| 5 | P2 | fix: transaction boundaries in ingest pipeline |
| 6 | P2 | fix: replace silent exception swallowing with structured error tracking |
| 7 | P2 | feat: streaming fetch_all_events + LIMIT on unbounded queries |
| 8 | P3 | refactor: add @db_tool decorator |
| 9 | P3 | refactor: split tools.py into domain modules |
| 10 | P3 | refactor: split data.py into domain route modules |
| 11 | P3 | refactor: replace module globals with FastAPI DI |
| 12 | P4 | feat: API key auth + cooldown guards |
| 13 | P4 | test: data.py route tests (~80-100 tests) |
| 14 | P4 | test: integration tests with testcontainers (~25-30 tests) |

**Total estimated effort:** ~16-20 hours across 14 commits.

---

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth mechanism | Single API key from `.env` | LAN-only, no user accounts needed |
| Rate limiting | Cooldown guards on 4 WCL endpoints | No internet traffic, just protect WCL quota |
| CORS origins | Hardcoded localhost:5173 + localhost:8000 | Only local dev + API server |
| Tool dedup | `@db_tool` decorator | Cleanest pattern, preserves LangChain `@tool` compatibility |
| DB schema changes | Alembic migration | Preserves existing data |
| Integration test DB | Docker testcontainers | Real PostgreSQL, tests ILIKE/PERCENTILE_CONT |
| God module split | By domain (player/raid/table/event) | Matches CLAUDE.md tool categories |
| DI scope | Routes only, not agent tools | LangChain tools can't use FastAPI `Depends()` |
