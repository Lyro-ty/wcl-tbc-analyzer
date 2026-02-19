# Shukketsu Raid Analyzer — Full Diagnostic Report

**Date:** 2026-02-19
**Branch:** main (HEAD: a2980e4)
**Review method:** 3 independent review iterations (Architecture, Bug Hunting, Completeness)
**Test baseline:** 713/713 passing, ruff lint clean

---

## Executive Summary

The codebase is well-architected for a monolith of this size, with strong layer separation, consistent patterns, and comprehensive test coverage. Three independent review passes found **4 bugs**, **10 important issues**, and **12 suggestions**. No security vulnerabilities were found — SQL injection, path traversal, and auth bypass vectors are all properly handled.

---

## CRITICAL BUGS (4)

### BUG-1: KeyError in cancelled casts display — `entry['count']` should be `entry['cancel_count']`

**File:** `code/shukketsu/agent/tools/event_tools.py:258`
**Impact:** Runtime KeyError when the LLM agent calls `get_cancelled_casts` and a player has cancelled spell data.

The JSON stored in `top_cancelled_json` uses key `cancel_count` (written in `cast_events.py:261`), but the tool reads `entry['count']`.

```python
# BEFORE (line 258)
f"{entry['count']} cancels"

# AFTER
f"{entry['cancel_count']} cancels"
```

### BUG-2: Case-sensitive player matching in progression snapshots

**File:** `code/shukketsu/pipeline/progression.py:35,99`
**Impact:** Progression snapshots silently return zero results when WCL returns a different casing than the registered character name.

```python
# BEFORE (lines 35, 99)
FightPerformance.player_name == character.name,

# AFTER
FightPerformance.player_name.ilike(character.name),
```

### BUG-3: Case-sensitive join in PLAYER_PARSE_DELTAS query

**File:** `code/shukketsu/db/queries/api.py:366`
**Impact:** Week-over-week parse deltas silently miss players whose name casing differs between two reports.

```sql
-- BEFORE (line 366)
JOIN prev_parses pp ON cp.player_name = pp.player_name

-- AFTER
JOIN prev_parses pp ON LOWER(cp.player_name) = LOWER(pp.player_name)
                   AND cp.encounter_name = pp.encounter_name
```

### BUG-4: Missing `sse-starlette` in pyproject.toml

**File:** `pyproject.toml`
**Impact:** Fresh `pip install` from manifest will work for all endpoints except `/api/analyze/stream`, which fails with `ImportError` at runtime.

```toml
# Add to dependencies list
"sse-starlette>=2.0",
```

---

## IMPORTANT ISSUES (10)

### IMP-1: Business logic duplicated between agent tools and API routes

4 algorithms are copy-pasted in both layers with identical thresholds:

| Logic | Agent tool location | API route location |
|-------|--------------------|--------------------|
| Consumable check | `event_tools.py:297-326` | `fights.py:213-243` |
| Rotation scoring | `event_tools.py:482-579` | `events.py:294-382` |
| DoT refresh | `event_tools.py:377-479` | `events.py:191-287` |
| Trinket grading | `table_tools.py:152-199` | `events.py:385-432` |

**Fix:** Extract into shared service functions in `pipeline/scoring.py`.

### IMP-2: REGRESSION_CHECK vs REGRESSION_CHECK_PLAYER — 95% duplicated SQL

**File:** `code/shukketsu/db/queries/player.py:203-305`

Two queries differ only by one WHERE clause. The nullable-parameter pattern (`CAST(:player_name AS text) IS NULL OR ...`) used elsewhere in the codebase would merge these into one.

### IMP-3: Case-sensitive self-join in REGRESSION_CHECK

**File:** `code/shukketsu/db/queries/player.py:241`

```sql
JOIN baseline b ON r.player_name = b.player_name
```

Should use `LOWER()` for consistency with all other player name joins.

### IMP-4: Duplicated `_THINK_PATTERN` regex

**Files:** `agent/utils.py:5` and `api/routes/analyze.py:15`

Same compiled regex defined in two files. `analyze.py` already imports `strip_think_tags` from `agent.utils` but defines its own copy of the pattern for the streaming buffer.

**Fix:** Export `_THINK_PATTERN` from `agent/utils.py` and import in `analyze.py`.

### IMP-5: API routes pass raw player names to ILIKE without wildcards (12+ endpoints)

All event endpoints in `events.py`, character endpoints in `characters.py`, and some fight endpoints in `fights.py` pass player names directly to ILIKE queries without `%` wrapping, while other endpoints in the same files DO wrap with wildcards. This inconsistency is confusing.

**Fix:** Decide on consistent behavior for API routes (exact match vs partial), apply uniformly.

### IMP-6: `structlog` declared as dependency but never imported

**File:** `pyproject.toml:23`

Zero files in `code/shukketsu/` import structlog. Every module uses stdlib `logging`.

**Fix:** Remove `"structlog>=24.0"` from dependencies.

### IMP-7: `langfuse` as non-optional dependency

**File:** `pyproject.toml:24`

Langfuse is conditionally imported only when `LANGFUSE__ENABLED=true`, but all deployments must install it.

**Fix:** Move to optional dependency group.

### IMP-8: Six separate module-level globals for dependency injection

**File:** `code/shukketsu/api/app.py` (lifespan)

`session_factory` is passed independently to 3 modules. Adding a new dependency requires touching both lifespan and the target module.

**Fix:** Consider a single `AppState` dataclass.

### IMP-9: Rankings rollback-then-commit can lose data

**File:** `code/shukketsu/pipeline/rankings.py:203-214`

If spec A succeeds, spec B fails (triggering rollback), and spec C succeeds, only spec C is committed. Spec A's data is lost.

**Fix:** Use per-spec savepoints or commit after each individual spec.

### IMP-10: `REPORTS_LIST` query has no LIMIT — unbounded result set

**File:** `code/shukketsu/db/queries/api.py:35-43`

Returns all reports with no pagination. Will degrade as the database grows.

**Fix:** Add `LIMIT 100` or pagination parameters.

---

## SUGGESTIONS (12)

| ID | File | Description |
|----|------|-------------|
| S-1 | `CLAUDE.md` | CORS docs say `allow_origins=["*"]` but code already restricts to localhost |
| S-2 | `CLAUDE.md` | Test count says "509" but suite now has 713 tests |
| S-3 | `events.py:464` | Inline `from sqlalchemy import text as sa_text` violates import-at-top rule |
| S-4 | `seed_encounters.py:47-49` | Two inline imports should be at module top |
| S-5 | `combatant_info.py:136` | `len(list(fights))` — fights is already a list, `len(fights)` suffices |
| S-6 | `event_tools.py:255-259` | Cancelled casts display uses spell ID but JSON includes `name` field |
| S-7 | `normalize.py` | Single one-liner function in its own module — could merge into `ingest.py` |
| S-8 | Phase analysis | Phase lookup + DPS estimation triplicated across 3 files |
| S-9 | `api/models.py` | 562 lines / ~40 models — could be split by domain like routes/queries |
| S-10 | `events.py:464-467` | Only inline SQL `text()` in the codebase — should move to `db/queries/` |
| S-11 | Magic 1.2 multiplier | Cooldown window +20% DPS gain hardcoded in 2 places — use named constant |
| S-12 | CLI scripts | All 7 scripts share identical engine/session/WCL boilerplate |

---

## POSITIVE FINDINGS

These areas were thoroughly reviewed and found to be solid:

- **Zero SQL injection vectors** — All queries use parameterized `text()`, no string interpolation
- **Zero resource leaks** — `@db_tool` decorator guarantees session cleanup; API uses `Depends(get_db)`; WCL client uses `async with`
- **Auth is timing-safe** — `hmac.compare_digest()` prevents timing attacks
- **Path traversal fixed** — SPA catch-all validates with `is_relative_to()`
- **Think-tag stripping comprehensive** — Applied in graph nodes (route, grade) AND API response layer, with buffered SSE handling
- **Retry decorators cover both HTTP and network errors** — WCL client and auth both handle 5xx + ConnectError + ReadTimeout
- **CASCADE deletes prevent orphans** — All FK relationships have `ondelete="CASCADE"`
- **Check constraints on percentages** — All percentage columns bounded 0-100
- **Indexes well-placed** — Composite indexes on all major join/filter patterns
- **Tests are high quality** — 713 tests, proper AsyncMock vs MagicMock usage, integration tests with testcontainers

---

## ARCHITECTURE GRADES

| Area | Grade | Notes |
|------|-------|-------|
| Module organization | A- | Clean splits; minor duplication |
| `@db_tool` abstraction | A | Excellent decorator design |
| Configuration | A | Proper pydantic-settings with nested models |
| Database layer | A- | Good indexes, constraints; one query duplication |
| API design | B+ | Clean route splits, but inconsistent wildcard wrapping |
| Pipeline architecture | A- | Robust error handling; clear data flow |
| Agent design | A | CRAG graph well-structured; tool registration clean |
| DI pattern | B | Functional but fragmented across 6 globals |
| Code duplication | B- | 4 algorithms duplicated between tools and routes |
| Test coverage | A | 713 tests, proper patterns |
| Security | A | No vulnerabilities found |
| Deployment readiness | B+ | Missing sse-starlette dep; langfuse should be optional |

**Overall: A-** — Production-quality codebase with a handful of bugs and maintenance risks to address.
