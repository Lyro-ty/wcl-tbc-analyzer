# Simplify Over-Engineering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce boilerplate and improve discoverability across agent tools, SQL queries, config, and app startup — without changing any runtime behavior.

**Architecture:** Extract shared helpers into `tool_utils.py`, reorganize `queries.py` into a domain-grouped package, clean up dead config code and Langfuse initialization. Module-level globals and AutoIngestService are left alone (justified below).

**Tech Stack:** Python 3.12, SQLAlchemy `text()`, langchain `@tool`, pydantic-settings, pytest with AsyncMock

---

## Honest Reassessment After Deep Dive

The original analysis flagged 5 areas. After reading every line of code, two items don't warrant changes:

**Module-Level Globals (Area 3) — LEAVE ALONE.** 6 `set_*()` calls wire dependencies during lifespan. This pattern touches every tool, route, and test. Refactoring to FastAPI `Depends()` would require reworking the entire `@db_tool` decorator and LangGraph's ToolNode integration. The current pattern works correctly and is tested. Risk far exceeds benefit.

**AutoIngestService (Area 5) — LEAVE ALONE.** The `_status`, `_stats`, and `_last_error` fields ARE surfaced via `GET /api/auto-ingest/status` (discovered in `routes/auto_ingest.py:22-25`). The exponential backoff, poll lock, and error tracking are all serving a real purpose. This is not over-engineered — it's a well-designed background service with an operational API.

**What we WILL do:**
1. Extract tool helpers (wildcards, grades, hints) — ~35 call sites simplified
2. Split `queries.py` (1,008 LOC) into a domain-grouped package — discoverability
3. Remove dead `AppConfig` class — zero references in non-test code
4. Simplify Langfuse initialization — replace function with 4-line try/except

---

## Task 1: Add Tool Helper Utilities

**Files:**
- Modify: `code/shukketsu/agent/tool_utils.py` (currently 99 lines)
- Create: `code/tests/agent/test_tool_utils.py`

**What to add to `tool_utils.py`:**
- `wildcard(value: str) -> str` — wraps value in `%...%`
- `wildcard_or_none(value: str | None) -> str | None` — wraps if not None, returns None otherwise
- `grade_above(value, tiers, default)` — first tier where `value >= threshold`
- `grade_below(value, tiers, default)` — first tier where `value < threshold`
- `TABLE_DATA_HINT` constant — the `--with-tables` error hint string
- `EVENT_DATA_HINT` constant — the `--with-events` error hint string

### Step 1: Write failing tests

```python
# code/tests/agent/test_tool_utils.py
"""Tests for agent tool utility helpers."""

from shukketsu.agent.tool_utils import (
    EVENT_DATA_HINT,
    TABLE_DATA_HINT,
    grade_above,
    grade_below,
    wildcard,
    wildcard_or_none,
)


class TestWildcard:
    def test_wraps_value(self):
        assert wildcard("Lyro") == "%Lyro%"

    def test_wraps_empty_string(self):
        assert wildcard("") == "%%"

    def test_preserves_spaces(self):
        assert wildcard("some name") == "%some name%"


class TestWildcardOrNone:
    def test_wraps_value(self):
        assert wildcard_or_none("Lyro") == "%Lyro%"

    def test_returns_none_for_none(self):
        assert wildcard_or_none(None) is None

    def test_returns_none_for_empty(self):
        assert wildcard_or_none("") is None

    def test_returns_none_for_whitespace(self):
        assert wildcard_or_none("  ") is None


class TestGradeAbove:
    """grade_above: first tier where value >= threshold (higher is better)."""

    def test_excellent(self):
        result = grade_above(
            95, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "EXCELLENT"

    def test_good(self):
        result = grade_above(
            87, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"

    def test_fair(self):
        result = grade_above(
            80, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "FAIR"

    def test_default(self):
        result = grade_above(
            50, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "NEEDS WORK"

    def test_exact_threshold(self):
        result = grade_above(
            85, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"

    def test_letter_grades(self):
        assert grade_above(92, [(90, "A"), (75, "B"), (60, "C"), (40, "D")], "F") == "A"
        assert grade_above(38, [(90, "A"), (75, "B"), (60, "C"), (40, "D")], "F") == "F"


class TestGradeBelow:
    """grade_below: first tier where value < threshold (lower is better)."""

    def test_excellent(self):
        result = grade_below(
            3, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "EXCELLENT"

    def test_good(self):
        result = grade_below(
            7, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"

    def test_default(self):
        result = grade_below(
            25, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "NEEDS WORK"

    def test_exact_threshold(self):
        # value == threshold means NOT below it, so should fall through
        result = grade_below(
            5, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"


class TestHintConstants:
    def test_table_hint_mentions_flag(self):
        assert "--with-tables" in TABLE_DATA_HINT

    def test_event_hint_mentions_flag(self):
        assert "--with-events" in EVENT_DATA_HINT
```

### Step 2: Run tests to verify they fail

Run: `python3 -m pytest code/tests/agent/test_tool_utils.py -v`
Expected: ImportError — the new functions/constants don't exist yet.

### Step 3: Implement the helpers

Add to the end of `code/shukketsu/agent/tool_utils.py`:

```python
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
```

### Step 4: Run tests to verify they pass

Run: `python3 -m pytest code/tests/agent/test_tool_utils.py -v`
Expected: All PASS.

### Step 5: Run full test suite for regressions

Run: `python3 -m pytest code/tests/ -v`
Expected: All 509 tests pass (no existing code changed yet).

### Step 6: Commit

```bash
git add code/shukketsu/agent/tool_utils.py code/tests/agent/test_tool_utils.py
git commit -m "feat: add wildcard, grade, and hint helpers to tool_utils"
```

---

## Task 2: Refactor player_tools.py to Use Helpers

**Files:**
- Modify: `code/shukketsu/agent/tools/player_tools.py` (417 lines)
- Modify: `code/tests/agent/test_tools.py` (verify existing tests still pass)

### Step 1: Add imports to player_tools.py

Add to the existing imports at the top of `player_tools.py`:

```python
from shukketsu.agent.tool_utils import wildcard
```

### Step 2: Replace all wildcard wrappings

Replace every `f"%{variable}%"` with `wildcard(variable)`. There are 18 instances in player_tools.py:

| Line | Old | New |
|------|-----|-----|
| 21 | `f"%{player_name}%"` | `wildcard(player_name)` |
| 22 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 27 | `f"%{player_name}%"` | `wildcard(player_name)` |
| 80 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 81 | `f"%{class_name}%"` | `wildcard(class_name)` |
| 82 | `f"%{spec_name}%"` | `wildcard(spec_name)` |
| 114 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 115 | `f"%{player_name}%"` | `wildcard(player_name)` |
| 116 | `f"%{class_name}%"` | `wildcard(class_name)` |
| 117 | `f"%{spec_name}%"` | `wildcard(spec_name)` |
| 180 | `f"%{character_name}%"` | `wildcard(character_name)` |
| 181 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 212 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 236 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 260 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 295 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 333 | `f"%{encounter_name}%"` | `wildcard(encounter_name)` |
| 381 | `f"%{player_name}%"` | `wildcard(player_name)` |

No grade logic to replace in player_tools (the regression direction check is business logic, not a grade scale).

### Step 3: Run tests

Run: `python3 -m pytest code/tests/agent/test_tools.py -v`
Expected: All pass — tool behavior unchanged.

### Step 4: Run lint

Run: `python3 -m ruff check code/shukketsu/agent/tools/player_tools.py`
Expected: Clean.

### Step 5: Commit

```bash
git add code/shukketsu/agent/tools/player_tools.py
git commit -m "refactor: use wildcard() helper in player_tools"
```

---

## Task 3: Refactor table_tools.py to Use Helpers

**Files:**
- Modify: `code/shukketsu/agent/tools/table_tools.py` (217 lines)

### Step 1: Add imports

```python
from shukketsu.agent.tool_utils import (
    TABLE_DATA_HINT,
    grade_above,
    grade_below,
    wildcard,
)
```

### Step 2: Replace wildcards (4 instances)

| Line | Old | New |
|------|-----|-----|
| 18 | `f"%{player_name}%"` | `wildcard(player_name)` |
| 69 | `f"%{player_name}%"` | `wildcard(player_name)` |
| 123 | `f"%{player_name}%"` | `wildcard(player_name)` |
| 178 | `f"%{player_name}%"` | `wildcard(player_name)` |

### Step 3: Replace hint strings (4 instances)

Replace the duplicated table data hint text at lines 22-26, 73-77, 127-131, and 204-208 with `TABLE_DATA_HINT`. For example:

**Before (lines 22-26):**
```python
return (
    f"No ability data found for '{player_name}' in fight "
    f"{fight_id} of report {report_code}. Table data may not "
    f"have been ingested yet (use pull-my-logs --with-tables "
    f"or pull-table-data to fetch it)."
)
```

**After:**
```python
return (
    f"No ability data found for '{player_name}' in fight "
    f"{fight_id} of report {report_code}. {TABLE_DATA_HINT}"
)
```

Apply the same pattern at lines 73-77, 127-131. Lines 204-208 (trinket tool) have slightly different wording — keep the custom message but use the hint constant for the shared portion.

### Step 4: Replace grade logic (3 tools)

**get_buff_analysis (lines 91-95):**
```python
# Before:
if r.uptime_pct >= 80:
    tier = "HIGH"
elif r.uptime_pct >= 50:
    tier = "MED"
else:
    tier = "LOW"

# After:
tier = grade_above(r.uptime_pct, [(80, "HIGH"), (50, "MED")], "LOW")
```

**get_overheal_analysis (lines 154-157):**
```python
# Before:
if oh_pct >= 40:
    flag = " [HIGH OVERHEAL]"
elif oh_pct >= 20:
    flag = " [MODERATE]"
else:
    flag = ""

# After:
flag = grade_above(oh_pct, [(40, " [HIGH OVERHEAL]"), (20, " [MODERATE]")], "")
```

**get_trinket_performance (lines 191-196):**
```python
# Before:
if uptime >= expected * 0.8:
    grade = "EXCELLENT"
elif uptime >= expected * 0.5:
    grade = "GOOD"
else:
    grade = "POOR"

# After (compute threshold inline):
grade = grade_above(uptime, [(expected * 0.8, "EXCELLENT"), (expected * 0.5, "GOOD")], "POOR")
```

### Step 5: Run tests and lint

Run: `python3 -m pytest code/tests/agent/test_tools.py -v && python3 -m ruff check code/shukketsu/agent/tools/table_tools.py`
Expected: All pass, clean lint.

### Step 6: Commit

```bash
git add code/shukketsu/agent/tools/table_tools.py
git commit -m "refactor: use helpers in table_tools (wildcards, grades, hints)"
```

---

## Task 4: Refactor event_tools.py to Use Helpers

**Files:**
- Modify: `code/shukketsu/agent/tools/event_tools.py` (803 lines — largest tool file)

### Step 1: Add imports

```python
from shukketsu.agent.tool_utils import (
    EVENT_DATA_HINT,
    grade_above,
    grade_below,
    wildcard,
    wildcard_or_none,
)
```

### Step 2: Replace wildcards (~17 instances)

Two patterns to handle:

**Direct wildcards** — replace `f"%{player_name}%"` with `wildcard(player_name)`:
Lines: 181, 229, 353, 397, 401, 424, 500, 504, 519, 527, 613, 741

**Conditional wildcards** — replace `f"%{player_name}%" if player_name else None` with `wildcard_or_none(player_name)`:
Lines: 24, 78, 130, 293, 668

### Step 3: Replace hint strings (~12 instances)

Replace the duplicated event data hint at lines 28-31, 82-86, 134-137, 185-189, 233-236, 297-300, 357-361, 405-407, 436-438, 566-568, 619-624, 672-673 with `EVENT_DATA_HINT`.

**Before (typical pattern):**
```python
return (
    f"No death data found for fight {fight_id} in report "
    f"{report_code}. Event data may not have been ingested yet "
    f"(use pull-my-logs --with-events to fetch it)."
)
```

**After:**
```python
return (
    f"No death data found for fight {fight_id} in report "
    f"{report_code}. {EVENT_DATA_HINT}"
)
```

### Step 4: Replace grade logic (5 tools)

**get_activity_report (lines 94-101):**
```python
# Before:
if r.gcd_uptime_pct >= 90:
    grade = "EXCELLENT"
elif r.gcd_uptime_pct >= 85:
    grade = "GOOD"
elif r.gcd_uptime_pct >= 75:
    grade = "FAIR"
else:
    grade = "NEEDS WORK"

# After:
grade = grade_above(
    r.gcd_uptime_pct,
    [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")],
    "NEEDS WORK",
)
```

**get_cooldown_efficiency (lines 151-156):**
```python
# Before:
if r.efficiency_pct < 70:
    flag = " [LOW]"
elif r.efficiency_pct >= 90:
    flag = " [GOOD]"
else:
    flag = " [OK]"

# After:
flag = grade_above(r.efficiency_pct, [(90, " [GOOD]"), (70, " [OK]")], " [LOW]")
```

**get_cancelled_casts (lines 247-254):**
```python
# Before:
if cancel_pct < 5:
    grade = "EXCELLENT"
elif cancel_pct < 10:
    grade = "GOOD"
elif cancel_pct < 20:
    grade = "FAIR"
else:
    grade = "NEEDS WORK"

# After:
grade = grade_below(
    cancel_pct,
    [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")],
    "NEEDS WORK",
)
```

**get_dot_management (lines 469-474):**
```python
# Before:
if early_pct < 10:
    grade = "GOOD"
elif early_pct < 25:
    grade = "FAIR"
else:
    grade = "NEEDS WORK"

# After:
grade = grade_below(early_pct, [(10, "GOOD"), (25, "FAIR")], "NEEDS WORK")
```

**get_rotation_score (lines 573-582):**
```python
# Before:
if score >= 90:
    letter = "A"
elif score >= 75:
    letter = "B"
elif score >= 60:
    letter = "C"
elif score >= 40:
    letter = "D"
else:
    letter = "F"

# After:
letter = grade_above(score, [(90, "A"), (75, "B"), (60, "C"), (40, "D")], "F")
```

### Step 5: Run tests and lint

Run: `python3 -m pytest code/tests/agent/test_tools.py -v && python3 -m ruff check code/shukketsu/agent/tools/event_tools.py`
Expected: All pass, clean lint.

### Step 6: Commit

```bash
git add code/shukketsu/agent/tools/event_tools.py
git commit -m "refactor: use helpers in event_tools (wildcards, grades, hints)"
```

---

## Task 5: Split queries.py into Domain Package

**Files:**
- Delete: `code/shukketsu/db/queries.py` (1,008 lines)
- Create: `code/shukketsu/db/queries/__init__.py` (re-exports all constants)
- Create: `code/shukketsu/db/queries/player.py` (~190 lines)
- Create: `code/shukketsu/db/queries/raid.py` (~130 lines)
- Create: `code/shukketsu/db/queries/table_data.py` (~80 lines)
- Create: `code/shukketsu/db/queries/event.py` (~200 lines)
- Create: `code/shukketsu/db/queries/api.py` (~400 lines — API-only queries)

### Step 1: Create the package directory

```bash
mkdir -p code/shukketsu/db/queries
```

### Step 2: Distribute queries by domain

**player.py** — Queries used by player agent tools + shared:
```
MY_PERFORMANCE, TOP_RANKINGS, COMPARE_TO_TOP, FIGHT_DETAILS, PROGRESSION,
DEATHS_AND_MECHANICS, SEARCH_FIGHTS, SPEC_LEADERBOARD, PERSONAL_BESTS,
PERSONAL_BESTS_BY_ENCOUNTER, WIPE_PROGRESSION, REGRESSION_CHECK,
MY_RECENT_KILLS, REGRESSION_CHECK_PLAYER
```

**raid.py** — Queries used by raid agent tools:
```
RAID_SUMMARY, RAID_VS_TOP_SPEED, COMPARE_TWO_RAIDS, RAID_EXECUTION_SUMMARY
```

**table_data.py** — Queries used by table-data agent tools:
```
ABILITY_BREAKDOWN, BUFF_ANALYSIS, OVERHEAL_ANALYSIS, PLAYER_BUFFS_FOR_TRINKETS
```

**event.py** — Queries used by event-data agent tools:
```
DEATH_ANALYSIS, CAST_ACTIVITY, COOLDOWN_EFFICIENCY, COOLDOWN_WINDOWS,
CANCELLED_CASTS, CONSUMABLE_CHECK, RESOURCE_USAGE, CAST_TIMELINE,
CAST_EVENTS_FOR_DOT_ANALYSIS, PLAYER_FIGHT_INFO, ENCHANT_GEM_CHECK,
GEAR_CHANGES, PHASE_BREAKDOWN, CAST_EVENTS_FOR_PHASES
```

**api.py** — Queries used only by REST API data routes:
```
REPORTS_LIST, ENCOUNTERS_LIST, CHARACTERS_LIST, CHARACTER_REPORTS,
REPORT_DEATHS, RAID_ABILITY_SUMMARY, FIGHT_ABILITIES, FIGHT_ABILITIES_PLAYER,
FIGHT_BUFFS, FIGHT_BUFFS_PLAYER, TABLE_DATA_EXISTS, CHARACTER_PROFILE,
CHARACTER_RECENT_PARSES, DASHBOARD_STATS, RECENT_REPORTS, CHARACTER_REPORT_DETAIL,
FIGHT_DEATHS, FIGHT_CAST_METRICS, FIGHT_COOLDOWNS, GEAR_SNAPSHOT,
NIGHT_SUMMARY_FIGHTS, NIGHT_SUMMARY_PLAYERS, WEEK_OVER_WEEK,
PLAYER_PARSE_DELTAS, EVENT_DATA_EXISTS
```

### Step 3: Create `__init__.py` that re-exports everything

```python
"""SQL query constants organized by domain.

Import from here for backwards compatibility:
    from shukketsu.db import queries as q
    q.MY_PERFORMANCE  # still works
"""

from shukketsu.db.queries.api import *  # noqa: F401, F403
from shukketsu.db.queries.event import *  # noqa: F401, F403
from shukketsu.db.queries.player import *  # noqa: F401, F403
from shukketsu.db.queries.raid import *  # noqa: F401, F403
from shukketsu.db.queries.table_data import *  # noqa: F401, F403
```

This means **no existing imports need to change**. `from shukketsu.db import queries as q` and `q.MY_PERFORMANCE` continue to work. The split is purely organizational.

### Step 4: Each domain file gets the same header

```python
"""Player-related SQL queries for agent tools."""

from sqlalchemy import text

__all__ = ["MY_PERFORMANCE", "TOP_RANKINGS", ...]
```

### Step 5: Verify no import breaks

Run: `python3 -m pytest code/tests/ -v`
Expected: All 509 tests pass.

Run: `python3 -m ruff check code/shukketsu/db/queries/`
Expected: Clean (the noqa comments suppress star-import warnings in __init__.py).

### Step 6: Commit

```bash
git add code/shukketsu/db/queries/
git rm code/shukketsu/db/queries.py  # git will handle file -> directory
git commit -m "refactor: split queries.py into domain-grouped package"
```

**Note:** `git rm` of the old file and `git add` of the new directory must happen in the same commit. Git tracks content, not files, so this will show as a rename/split.

---

## Task 6: Simplify Langfuse Initialization

**Files:**
- Modify: `code/shukketsu/api/app.py` (lines 25-41 and 71-79)
- Modify: `code/tests/api/test_app.py` (if it tests _init_langfuse)

### Step 1: Replace `_init_langfuse` function with inline try/except

**Before (lines 25-41):**
```python
CallbackHandler = None


def _init_langfuse(public_key: str, secret_key: str, host: str):
    global CallbackHandler
    from langfuse import Langfuse

    Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    if CallbackHandler is None:
        import langfuse.langchain

        CallbackHandler = langfuse.langchain.CallbackHandler
    return CallbackHandler
```

**After:**
Remove the function entirely. In the lifespan where it was called (lines 71-79):

**Before (lifespan, lines 71-79):**
```python
if settings.langfuse.enabled:
    cb_handler_cls = _init_langfuse(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key.get_secret_value(),
        host=settings.langfuse.host,
    )
    set_langfuse_handler(cb_handler_cls)
    logger.info("Langfuse tracing enabled")
```

**After:**
```python
if settings.langfuse.enabled:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler as LangfuseCB

    Langfuse(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key.get_secret_value(),
        host=settings.langfuse.host,
    )
    set_langfuse_handler(LangfuseCB)
    logger.info("Langfuse tracing enabled")
```

This removes the global `CallbackHandler` variable, the `_init_langfuse` function, and the lazy-import indirection.

### Step 2: Run tests

Run: `python3 -m pytest code/tests/ -v`
Expected: All pass.

### Step 3: Commit

```bash
git add code/shukketsu/api/app.py
git commit -m "refactor: inline langfuse init, remove _init_langfuse function"
```

---

## Task 7: Remove Unused AppConfig

**Files:**
- Modify: `code/shukketsu/config.py` (remove AppConfig class, lines 32-35)
- Modify: `code/tests/test_config.py` (remove any AppConfig references)

### Step 1: Verify AppConfig is truly unused

The exploration found **zero references** to `settings.app.` outside test files. Confirm:

```bash
grep -r "settings\.app\." code/shukketsu/ --include="*.py"
```

Expected: No results (only test files reference it).

### Step 2: Remove AppConfig

Delete the class definition (lines 32-35 of config.py):
```python
class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = ""
```

And remove `app: AppConfig = AppConfig()` from Settings class.

**Important:** Check if `deps.py` `verify_api_key` uses `settings.app.api_key`. If it does, move the `api_key` field to the top-level Settings class:

```python
class Settings(BaseSettings):
    api_key: str = ""  # moved from AppConfig
    # ...
```

And update `deps.py` to use `settings.api_key` instead of `settings.app.api_key`.

### Step 3: Update test_config.py

Remove any assertions about `settings.app` and update references.

### Step 4: Run tests

Run: `python3 -m pytest code/tests/test_config.py -v && python3 -m pytest code/tests/ -v`
Expected: All pass.

### Step 5: Commit

```bash
git add code/shukketsu/config.py code/tests/test_config.py
# Also add deps.py if verify_api_key was updated
git commit -m "refactor: remove unused AppConfig, move api_key to top-level Settings"
```

---

## Task 8: Final Verification and Lint

### Step 1: Run full test suite

Run: `python3 -m pytest code/tests/ -v`
Expected: All 509+ tests pass.

### Step 2: Run linter on all changed files

Run: `python3 -m ruff check code/`
Expected: Clean.

### Step 3: Verify no behavior changes

The entire refactor should be behavior-preserving:
- Tool output strings are identical (same format, same content)
- SQL queries are identical (just moved to different files)
- Config loads identically (same env vars, same defaults)
- Langfuse init produces the same result
- All existing `from shukketsu.db import queries as q` imports work unchanged

### Step 4: Commit any remaining lint fixes

```bash
git add -A && git commit -m "chore: final lint fixes after over-engineering cleanup"
```

---

## Impact Summary

| Area | Before | After | LOC Change |
|------|--------|-------|------------|
| Tool wildcards | 35x `f"%{x}%"` | 35x `wildcard(x)` | +60 (helpers), -0 (same line count, clearer) |
| Grade logic | 8 if/elif blocks | 8 one-liners | ~-60 lines |
| Hint strings | 16 duplicated strings | 2 constants | ~-40 lines |
| queries.py | 1 file, 1008 LOC | 5 domain files + __init__ | 0 net (reorganized) |
| Langfuse init | function + global | 6-line inline block | -15 lines |
| AppConfig | dead class | removed | -6 lines |
| **Total** | | | ~-120 LOC net, +much better discoverability |

## What We Deliberately Did NOT Change

1. **Module-level globals / pseudo-DI** — Works correctly, tested, would require reworking the entire LangGraph tool integration. Leave alone.
2. **AutoIngestService lifecycle** — All state variables (`_status`, `_stats`, `_last_error`) are surfaced via `GET /api/auto-ingest/status`. The complexity is justified by the operational API. Leave alone.
3. **raid_tools.py** — Only 162 lines, no wildcards (uses direct report_code params), no grade logic. Nothing to simplify.
