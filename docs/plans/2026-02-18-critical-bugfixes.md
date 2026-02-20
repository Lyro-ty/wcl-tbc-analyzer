# Critical Bugfix Sweep Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all data-loss, agent-logic, security, concurrency, and database bugs identified in the code review, organized by priority tier.

**Architecture:** Surgical fixes across pipeline, agent, API, and DB layers. No new features. Each task is a self-contained commit targeting a specific bug class.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, SQLAlchemy 2.0 async, PostgreSQL 16, Alembic

---

## Task 1: Fix encounter metadata corruption on re-ingest

**Files:**
- Modify: `code/shukketsu/pipeline/ingest.py:126-137`
- Test: `code/tests/pipeline/test_ingest.py`

**Context:** `session.merge(Encounter(id=eid, zone_id=0, zone_name="Unknown"))` overwrites properly-seeded encounters. Every re-ingest corrupts `zone_id` and `zone_name` back to 0/"Unknown".

**Step 1: Write the failing test**

```python
class TestEncounterStubMerge:
    async def test_existing_encounter_not_overwritten(self):
        """Merging a stub should NOT overwrite existing zone data."""
        from shukketsu.db.models import Encounter

        session = AsyncMock()
        # Simulate encounter already exists in DB
        existing = Encounter(
            id=201107, name="Patchwerk", zone_id=2017,
            zone_name="Naxxramas", difficulty=3,
        )
        session.get = AsyncMock(return_value=existing)
        session.merge = MagicMock()

        # After fix: ingest should check existence before merging
        # The merge should NOT be called for existing encounters
```

**Step 2: Implement the fix**

In `code/shukketsu/pipeline/ingest.py`, replace the encounter merge loop (lines 126-137) with:

```python
    for eid in encounter_ids:
        # Only insert stub if encounter doesn't already exist
        existing = await session.get(Encounter, eid)
        if existing is not None:
            continue
        fight_data = next(
            fd for fd in report_info["fights"] if fd.get("encounterID") == eid
        )
        await session.merge(Encounter(
            id=eid,
            name=fight_data.get("name", f"Unknown ({eid})"),
            zone_id=0,
            zone_name="Unknown",
            difficulty=fight_data.get("difficulty", 0),
        ))
```

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/pipeline/test_ingest.py -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/pipeline/ingest.py code/tests/pipeline/test_ingest.py
git commit -m "fix: prevent encounter metadata corruption on re-ingest"
```

---

## Task 2: Fix table data partial-delete data loss

**Files:**
- Modify: `code/shukketsu/pipeline/table_data.py:120-183`
- Test: `code/tests/pipeline/test_table_data.py`

**Context:** All ability_metrics + buff_uptimes are deleted upfront. If a later API call fails, old data is gone with nothing to replace it. Fix: move deletes to per-type (delete immediately before each type's insert).

**Step 1: Write the failing test**

```python
class TestTableDataPartialFailure:
    async def test_failed_type_preserves_other_types(self):
        """If one WCL API call fails, data from other types should survive."""
        # Mock WCL to fail on Buffs but succeed on DamageDone/Healing
        # After fix: DamageDone/Healing data should be present,
        # Buffs data should be the old data (not deleted)
```

**Step 2: Implement the fix**

Move the blanket delete from lines 120-126 into the per-type loop. Each type deletes only its own rows right before inserting:

```python
    for wcl_type, metric_type, parse_kind in data_type_config:
        try:
            raw_data = await wcl.query(...)
            ...
            # Delete only THIS type's rows right before insert
            if parse_kind == "abilities":
                await session.execute(
                    delete(AbilityMetric).where(
                        AbilityMetric.fight_id == fight.id,
                        AbilityMetric.metric_type == metric_type,
                    )
                )
            else:
                await session.execute(
                    delete(BuffUptime).where(
                        BuffUptime.fight_id == fight.id,
                        BuffUptime.metric_type == metric_type,
                    )
                )
            # Insert new rows
            ...
        except Exception:
            logger.exception(...)
            continue
```

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/pipeline/test_table_data.py -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/pipeline/table_data.py code/tests/pipeline/test_table_data.py
git commit -m "fix: move table data deletes to per-type to prevent partial data loss"
```

---

## Task 3: Remove inner exception swallowing in event pipelines

**Files:**
- Modify: `code/shukketsu/pipeline/cast_events.py:355-360`
- Modify: `code/shukketsu/pipeline/death_events.py:130-135`
- Modify: `code/shukketsu/pipeline/resource_events.py` (similar pattern)
- Test: `code/tests/pipeline/test_cast_events.py`
- Test: `code/tests/pipeline/test_death_events.py`

**Context:** Inner `except Exception: return 0` blocks swallow errors. The outer handler in `ingest.py` that populates `enrichment_errors` never fires. Combined with delete-before-fetch, this causes silent data loss.

**Step 1: Remove inner exception handlers**

In `cast_events.py`, remove the try/except wrapper (lines 295, 355-360), letting the function body run without catching. Same for `death_events.py` (lines 101, 130-135) and `resource_events.py` (similar pattern).

Before (cast_events.py):
```python
    try:
        # ... all the logic ...
        return total_rows
    except Exception:
        logger.exception(...)
        return 0
```

After:
```python
    # ... all the logic ...
    return total_rows
```

The outer handler in `ingest.py:244-256` will now correctly catch failures and populate `enrichment_errors`.

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/pipeline/ -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/pipeline/cast_events.py code/shukketsu/pipeline/death_events.py code/shukketsu/pipeline/resource_events.py
git commit -m "fix: remove inner exception swallowing in event pipelines

Let errors propagate to ingest.py so enrichment_errors is populated
correctly. Previously, delete-then-fetch failures were silently
swallowed, causing data loss."
```

---

## Task 4: Cap CHECK constraint fields to prevent IntegrityError

**Files:**
- Modify: `code/shukketsu/pipeline/cast_events.py:183`
- Modify: `code/shukketsu/pipeline/resource_events.py:105`
- Test: `code/tests/pipeline/test_cast_events.py`
- Test: `code/tests/pipeline/test_resource_events.py`

**Context:** `efficiency_pct` can exceed 100% (pre-cast cooldowns), `time_at_zero_pct` can exceed 100% (events outside fight window). Both tables have `CHECK(... <= 100)`. The IntegrityError gets swallowed by inner handlers (fixed in Task 3), but we should still cap the values.

**Step 1: Write failing tests**

```python
class TestEfficiencyPctCap:
    def test_efficiency_capped_at_100(self):
        """Pre-cast cooldowns can produce >100% efficiency."""
        # 3 uses of a 3-minute cooldown in a 5-minute fight
        # max_possible = floor(300000/180000) + 1 = 2
        # efficiency = 3/2 * 100 = 150% -> should cap at 100.0

class TestTimeAtZeroCap:
    def test_time_at_zero_capped_at_100(self):
        """Events outside fight window can push past 100%."""
```

**Step 2: Implement the fix**

In `cast_events.py:183`, change:
```python
efficiency = (times_used / max_possible * 100) if max_possible > 0 else 0.0
```
to:
```python
efficiency = min((times_used / max_possible * 100) if max_possible > 0 else 0.0, 100.0)
```

In `resource_events.py:105`, change:
```python
time_at_zero_pct = round(time_at_zero_ms / fight_duration_ms * 100, 1)
```
to:
```python
time_at_zero_pct = min(round(time_at_zero_ms / fight_duration_ms * 100, 1), 100.0)
```

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/pipeline/test_cast_events.py code/tests/pipeline/test_resource_events.py -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/pipeline/cast_events.py code/shukketsu/pipeline/resource_events.py code/tests/pipeline/test_cast_events.py code/tests/pipeline/test_resource_events.py
git commit -m "fix: cap efficiency_pct and time_at_zero_pct at 100.0

Prevents CHECK constraint violations from pre-cast cooldowns and
events outside fight window."
```

---

## Task 5: Fix CRAG grader losing user question with 3+ tools

**Files:**
- Modify: `code/shukketsu/agent/graph.py:98`
- Test: `code/tests/agent/test_graph.py`

**Context:** `state["messages"][-3:]` after 4+ tool calls gives only ToolMessages. Grader evaluates with zero knowledge of the question.

**Step 1: Write the failing test**

```python
class TestGradeResultsContext:
    async def test_grader_sees_user_question_with_many_tools(self):
        """When 4+ tools are called, grader should still see user question."""
        state = {
            "messages": [
                HumanMessage(content="How did Lyro do on Patchwerk?"),
                AIMessage(content="", tool_calls=[...]),  # 4 tool calls
                ToolMessage(content="result1", tool_call_id="1"),
                ToolMessage(content="result2", tool_call_id="2"),
                ToolMessage(content="result3", tool_call_id="3"),
                ToolMessage(content="result4", tool_call_id="4"),
            ],
            "retry_count": 0,
        }
        # After fix: _format_messages output should contain "How did Lyro"
```

**Step 2: Implement the fix**

Replace line 98 in `graph.py`:
```python
    recent = state["messages"][-3:] if len(state["messages"]) > 3 else state["messages"]
```
with:
```python
    # Always include the original user question + latest tool results
    original = [m for m in state["messages"] if isinstance(m, HumanMessage)][:1]
    tail = state["messages"][-3:]
    recent = original + [m for m in tail if m not in original]
```

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/agent/test_graph.py -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/agent/graph.py code/tests/agent/test_graph.py
git commit -m "fix: grader always includes original user question

Previously, state['messages'][-3:] with 4+ tool calls gave only
ToolMessages, causing the grader to evaluate relevance with no
knowledge of what was asked."
```

---

## Task 6: Fix query_database retry sending AIMessage instead of HumanMessage

**Files:**
- Modify: `code/shukketsu/agent/graph.py:64-85` (query_database function)
- Test: `code/tests/agent/test_graph.py`

**Context:** After rewrite, `state["messages"][-1]` is an AIMessage. The query node sends `[SystemMessage, AIMessage]` to the LLM -- no user turn.

**Step 1: Implement the fix**

In `query_database`, replace `user_msg = state["messages"][-1]` with logic that always finds the original HumanMessage:

```python
    # Always use the original user question (not the rewrite AIMessage)
    user_msg = next(
        (m for m in state["messages"] if isinstance(m, HumanMessage)),
        state["messages"][-1],
    )
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/agent/test_graph.py -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/agent/graph.py code/tests/agent/test_graph.py
git commit -m "fix: query_database always uses original HumanMessage on retry

After rewrite, state['messages'][-1] is an AIMessage. The LLM
received [System, Assistant] with no user turn, breaking tool calls."
```

---

## Task 7: Add LLM retry logic

**Files:**
- Modify: `code/shukketsu/agent/llm.py`
- Test: `code/tests/agent/test_llm.py` (new)

**Context:** WCL client has tenacity retries but LLM calls have zero. A transient ollama 502 kills the entire agent run. This violates the project's own coding rule.

**Step 1: Implement retry wrapper**

```python
from langchain_openai import ChatOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from shukketsu.config import Settings


def create_llm(settings: Settings) -> ChatOpenAI:
    llm = ChatOpenAI(
        model=settings.llm.model,
        base_url=settings.llm.base_url,
        api_key=settings.llm.api_key,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        extra_body={"options": {"num_ctx": settings.llm.num_ctx}},
    )
    # Wrap ainvoke with retry logic for transient errors
    original_ainvoke = llm.ainvoke

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _ainvoke_with_retry(*args, **kwargs):
        return await original_ainvoke(*args, **kwargs)

    llm.ainvoke = _ainvoke_with_retry
    return llm
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/agent/ -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/agent/llm.py code/tests/agent/test_llm.py
git commit -m "fix: add tenacity retry to LLM ainvoke for transient errors

Wraps ainvoke with retry on ConnectionError, TimeoutError, OSError
matching the project's retry pattern for external API calls."
```

---

## Task 8: Fix error leakage in all API endpoints

**Files:**
- Modify: `code/shukketsu/api/routes/data/reports.py`
- Modify: `code/shukketsu/api/routes/data/fights.py`
- Modify: `code/shukketsu/api/routes/data/characters.py`
- Modify: `code/shukketsu/api/routes/data/rankings.py`
- Modify: `code/shukketsu/api/routes/data/comparison.py`
- Modify: `code/shukketsu/api/routes/data/events.py`
- Modify: `code/shukketsu/api/routes/analyze.py:147`

**Context:** 48 endpoints do `raise HTTPException(500, detail=str(e))`. SQLAlchemy errors include full query text, table names, connection details. SSE error handler also leaks.

**Step 1: Implement the fix**

In every route file, replace all instances of:
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e)) from e
```
with:
```python
except Exception:
    logger.exception("Request failed")
    raise HTTPException(status_code=500, detail="Internal server error")
```

Ensure each file imports `logging` and has `logger = logging.getLogger(__name__)`.

For `analyze.py:147`, change:
```python
yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
```
to:
```python
yield {"event": "error", "data": json.dumps({"detail": "Analysis failed"})}
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/api/ -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/api/routes/
git commit -m "fix: replace str(e) with generic error in all 500 responses

Prevents leaking SQL query text, table names, and connection details
to clients. Real errors are now logged server-side."
```

---

## Task 9: Add rate limiting and input validation to analyze endpoints

**Files:**
- Modify: `code/shukketsu/api/routes/analyze.py`
- Modify: `code/shukketsu/api/deps.py:56`

**Context:** No rate limit on LLM endpoints (DoS vector). No max_length on question. API key comparison vulnerable to timing attack.

**Step 1: Add input validation + rate limit**

In `analyze.py`, add:
```python
import asyncio

from pydantic import Field

class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

_llm_semaphore = asyncio.Semaphore(2)

@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[cooldown("analyze", 10)])
async def analyze(request: AnalyzeRequest):
    async with _llm_semaphore:
        ...

@router.post("/analyze/stream", dependencies=[cooldown("analyze_stream", 10)])
async def analyze_stream(request: AnalyzeRequest):
    ...
```

**Step 2: Fix timing attack**

In `deps.py:56`, replace:
```python
if not provided or provided != configured_key:
```
with:
```python
import hmac
if not provided or not hmac.compare_digest(provided, configured_key):
```

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/api/ -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/api/routes/analyze.py code/shukketsu/api/deps.py
git commit -m "fix: add rate limit, input validation, and timing-safe auth

- AnalyzeRequest.question: max_length=2000
- cooldown + semaphore on /analyze and /analyze/stream
- hmac.compare_digest for API key comparison"
```

---

## Task 10: Fix auto-ingest concurrency + missing my_character_names

**Files:**
- Modify: `code/shukketsu/pipeline/auto_ingest.py`
- Test: `code/tests/pipeline/test_auto_ingest.py`

**Context:** (a) `trigger_now()` and `_poll_loop` can run `_poll_once()` concurrently. (b) Auto-ingest doesn't pass character names, so `is_my_character` is always False.

**Step 1: Add asyncio.Lock + query my_characters**

```python
class AutoIngestService:
    def __init__(self, ...):
        ...
        self._poll_lock = asyncio.Lock()

    async def _poll_once(self):
        async with self._poll_lock:
            await self._poll_once_inner()

    async def _poll_once_inner(self):
        # ... existing _poll_once logic ...
        # Before the ingest loop, query my_characters:
        async with self._session_factory() as session:
            from shukketsu.db.models import MyCharacter
            result = await session.execute(select(MyCharacter.name))
            my_names = {row[0] for row in result}

        # Pass to ingest_report:
        await ingest_report(
            wcl, session, code,
            my_character_names=my_names,
            ingest_tables=cfg.with_tables,
            ingest_events=cfg.with_events,
        )

    async def trigger_now(self) -> dict:
        if self._poll_lock.locked():
            return {"status": "already_running", "message": "Poll already in progress"}
        self._trigger_task = asyncio.create_task(self._poll_once())
        return {"status": "triggered", "message": "Poll started in background"}
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/pipeline/test_auto_ingest.py -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/pipeline/auto_ingest.py code/tests/pipeline/test_auto_ingest.py
git commit -m "fix: add poll mutex and pass my_character_names in auto-ingest

- asyncio.Lock prevents concurrent _poll_once execution
- Queries my_characters table and passes names to ingest_report
  so is_my_character is correctly set"
```

---

## Task 11: Fix rankings session corruption after DB error

**Files:**
- Modify: `code/shukketsu/pipeline/rankings.py:203-210`
- Modify: `code/shukketsu/pipeline/speed_rankings.py:148-151`

**Context:** If `fetch_rankings_for_spec()` throws a DBAPIError, session enters invalid state. `except Exception: continue` catches it, but next `session.execute()` fails with `PendingRollbackError`.

**Step 1: Add rollback in exception handler**

In `rankings.py:203-210`, after the except block, add rollback:
```python
                except Exception as e:
                    error_msg = (
                        f"{spec.class_name} {spec.spec_name} on {enc_id} ({metric}): {e}"
                    )
                    result.errors.append(error_msg)
                    logger.error(
                        "[%d/%d] Error: %s", progress, total_combos, error_msg
                    )
                    await session.rollback()
```

Same in `speed_rankings.py:148-151`:
```python
        except Exception as e:
            error_msg = f"encounter {enc_id}: {e}"
            result.errors.append(error_msg)
            logger.error("[%d/%d] Error: %s", i, total, error_msg)
            await session.rollback()
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/pipeline/test_rankings.py code/tests/pipeline/test_speed_rankings.py -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/pipeline/rankings.py code/shukketsu/pipeline/speed_rankings.py
git commit -m "fix: rollback session after DB errors in rankings ingestion

Prevents PendingRollbackError on subsequent iterations when a
DBAPIError invalidates the session transaction."
```

---

## Task 12: Fix case-sensitive JOINs in SQL queries

**Files:**
- Modify: `code/shukketsu/db/queries.py:438,455,941`

**Context:** Three queries use exact `=` in JOIN conditions while WHERE uses ILIKE. This violates the project's case-insensitive matching rule.

**Step 1: Fix the JOINs**

`queries.py:438` - CHARACTER_PROFILE:
```sql
LEFT JOIN fight_performances fp ON LOWER(fp.player_name) = LOWER(mc.name)
```

`queries.py:455` - CHARACTER_RECENT_PARSES:
```sql
JOIN my_characters mc ON LOWER(mc.name) = LOWER(fp.player_name)
```

`queries.py:941` - COOLDOWN_WINDOWS:
```sql
JOIN fight_performances fp
    ON fp.fight_id = f.id AND LOWER(fp.player_name) = LOWER(cu.player_name)
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/ -v -k "character_profile or character_recent or cooldown_windows"
```

**Step 3: Commit**

```bash
git add code/shukketsu/db/queries.py
git commit -m "fix: use LOWER() in JOIN conditions for case-insensitive matching

CHARACTER_PROFILE, CHARACTER_RECENT_PARSES, and COOLDOWN_WINDOWS
used exact = in JOINs while WHERE used ILIKE, causing silent
data loss with mismatched casing."
```

---

## Task 13: Fix Langfuse handler shared across concurrent requests

**Files:**
- Modify: `code/shukketsu/api/app.py:77-78`
- Modify: `code/shukketsu/api/routes/analyze.py:21-26,64-66`

**Context:** A single `CallbackHandler` instance is shared across all concurrent requests. Store the class, not the instance.

**Step 1: Implement the fix**

In `app.py`, change:
```python
langfuse_handler = cb_handler_cls()
set_langfuse_handler(langfuse_handler)
```
to:
```python
set_langfuse_handler_cls(cb_handler_cls)
```

In `analyze.py`, rename `_langfuse_handler` to `_langfuse_handler_cls` and create fresh instance per request:
```python
_langfuse_handler_cls = None

def set_langfuse_handler_cls(cls):
    global _langfuse_handler_cls
    _langfuse_handler_cls = cls

def _get_langfuse_handler():
    return _langfuse_handler_cls() if _langfuse_handler_cls else None
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/api/ -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/api/app.py code/shukketsu/api/routes/analyze.py
git commit -m "fix: create fresh Langfuse handler per request

Previously shared a single CallbackHandler instance across all
concurrent requests, causing interleaved/corrupt trace data."
```

---

## Task 14: Add logging to tool error handler + fix wrong CLI flag

**Files:**
- Modify: `code/shukketsu/agent/tool_utils.py:39-40`
- Modify: `code/shukketsu/agent/tools/event_tools.py:624`

**Context:** (a) Tool errors are caught but never logged. (b) `get_gear_changes` says `--with-tables` but gear data comes from `--with-events`.

**Step 1: Add logging to db_tool**

In `tool_utils.py`, add at top:
```python
import logging

logger = logging.getLogger(__name__)
```

Change lines 39-40 from:
```python
        except Exception as e:
            return f"Error retrieving data: {e}"
```
to:
```python
        except Exception as e:
            logger.exception("Tool error in %s", fn.__name__)
            return f"Error retrieving data: {e}"
```

**Step 2: Fix wrong CLI flag**

In `event_tools.py:624`, change:
```python
f"(use pull-my-logs --with-tables to fetch it)."
```
to:
```python
f"(use pull-my-logs --with-events to fetch it)."
```

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/agent/ -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/agent/tool_utils.py code/shukketsu/agent/tools/event_tools.py
git commit -m "fix: add logging to tool errors + correct --with-events flag

- db_tool decorator now logs exceptions before returning error string
- get_gear_changes referenced --with-tables but gear comes from --with-events"
```

---

## Task 15: Deduplicate _strip_think_tags + remove dead code

**Files:**
- Modify: `code/shukketsu/agent/graph.py:27-32`
- Modify: `code/shukketsu/api/routes/analyze.py:12-17`
- Create: `code/shukketsu/agent/utils.py`
- Delete dead code: `code/shukketsu/db/engine.py:28-34`

**Context:** (a) `_strip_think_tags` is copy-pasted in two files. (b) `engine.py:get_session()` is never imported.

**Step 1: Extract _strip_think_tags**

Create `code/shukketsu/agent/utils.py`:
```python
"""Shared utilities for the agent layer."""

import re

_THINK_PATTERN = re.compile(r"^.*?</think>\s*", flags=re.DOTALL)


def strip_think_tags(text: str) -> str:
    """Strip Nemotron's leaked reasoning/think tags from output."""
    return _THINK_PATTERN.sub("", text)
```

Update `graph.py` and `analyze.py` to import from utils instead of defining locally.

**Step 2: Remove dead `get_session`**

Delete lines 28-34 from `engine.py` and the unused `asynccontextmanager` / `AsyncGenerator` imports.

**Step 3: Run tests**

```bash
python3 -m pytest code/tests/ -v
```

**Step 4: Commit**

```bash
git add code/shukketsu/agent/utils.py code/shukketsu/agent/graph.py code/shukketsu/api/routes/analyze.py code/shukketsu/db/engine.py
git commit -m "refactor: deduplicate _strip_think_tags + remove dead get_session"
```

---

## Task 16: Add missing database indexes (Alembic migration)

**Files:**
- Create: `code/alembic/versions/XXX_add_missing_indexes.py`
- Reference: `code/shukketsu/db/models.py`

**Context:** Missing indexes on speed_rankings.encounter_id, fight_performances.is_my_character (partial), reports.start_time.

**Step 1: Generate and edit migration**

```bash
cd /home/lyro/nvidia-workbench/wcl-tbc-analyzer
alembic revision --autogenerate -m "add missing indexes"
```

Then edit the generated migration to add:

```python
def upgrade():
    op.create_index(
        "ix_speed_rankings_encounter_id",
        "speed_rankings", ["encounter_id"],
    )
    op.create_index(
        "ix_fight_performances_my_char",
        "fight_performances", ["is_my_character"],
        postgresql_where=text("is_my_character = true"),
    )
    op.create_index(
        "ix_reports_start_time",
        "reports", ["start_time"],
    )

def downgrade():
    op.drop_index("ix_reports_start_time")
    op.drop_index("ix_fight_performances_my_char")
    op.drop_index("ix_speed_rankings_encounter_id")
```

Also update `models.py` SpeedRanking `__table_args__` to include the index for ORM consistency.

**Step 2: Test migration**

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**Step 3: Commit**

```bash
git add code/alembic/versions/ code/shukketsu/db/models.py
git commit -m "feat: add indexes on speed_rankings, is_my_character, start_time"
```

---

## Task 17: Add cooldown to table-data and event-data POST endpoints

**Files:**
- Modify: `code/shukketsu/api/routes/data/reports.py` (lines ~199, ~237)

**Context:** Both endpoints trigger WCL API calls but have no cooldown, unlike `/ingest` which has `cooldown("ingest", 120)`.

**Step 1: Add cooldown dependency**

```python
@router.post("/reports/{report_code}/table-data", dependencies=[cooldown("table_data", 60)])
async def fetch_table_data(...):
    ...

@router.post("/reports/{report_code}/event-data", dependencies=[cooldown("event_data", 60)])
async def fetch_event_data(...):
    ...
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/api/test_data_reports.py -v
```

**Step 3: Commit**

```bash
git add code/shukketsu/api/routes/data/reports.py
git commit -m "fix: add cooldown to table-data and event-data POST endpoints"
```

---

## Task 18: Clamp resolve_my_fights count parameter

**Files:**
- Modify: `code/shukketsu/agent/tools/player_tools.py` (resolve_my_fights function)
- Test: `code/tests/agent/test_tools.py`

**Context:** The `count` parameter is passed directly to `LIMIT :limit`. LLM controls this parameter with no upper bound.

**Step 1: Add clamping**

At the top of `resolve_my_fights`, add:
```python
count = min(max(count, 1), 25)
```

**Step 2: Run tests**

```bash
python3 -m pytest code/tests/agent/test_tools.py -v -k "resolve"
```

**Step 3: Commit**

```bash
git add code/shukketsu/agent/tools/player_tools.py
git commit -m "fix: clamp resolve_my_fights count to 1-25"
```

---

## Final verification

After all tasks are complete:

```bash
# Full test suite
python3 -m pytest code/tests/ -v

# Lint
python3 -m ruff check code/

# Verify no regressions in integration tests
python3 -m pytest code/tests/integration/ -v -m integration
```
