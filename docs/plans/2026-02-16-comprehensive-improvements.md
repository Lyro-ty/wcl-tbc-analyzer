# Comprehensive Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address all identified quality, reliability, and UX improvements across the Shukketsu Raid Analyzer — database indexes, agent correctness, API hardening, dead code cleanup, and LLM configuration.

**Architecture:** Bottom-up approach — fix the data layer first (indexes), then agent internals (think-tag stripping, tool arg normalization, dead state fields), then API improvements (health check, LLM config, batch endpoint), then cleanup (dead code removal). Each task is independent or has explicit ordering where needed.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, FastAPI, LangGraph, langchain-openai, PostgreSQL 16, pytest

---

## Phase 1: Database Performance (Indexes)

### Task 1: Add database indexes via Alembic migration

**Files:**
- Create: `code/alembic/versions/003_add_performance_indexes.py`

**Step 1: Create the migration file**

```python
"""add performance indexes

Revision ID: 003
Revises: 002
Create Date: 2026-02-16

"""
from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # fight_performances — most queried table, every tool call touches it
    op.create_index(
        "ix_fight_performances_fight_id",
        "fight_performances",
        ["fight_id"],
    )
    op.create_index(
        "ix_fight_performances_player_name",
        "fight_performances",
        ["player_name"],
    )
    op.create_index(
        "ix_fight_performances_class_spec",
        "fight_performances",
        ["player_class", "player_spec"],
    )

    # fights — filtered by report_code and encounter_id in nearly every query
    op.create_index(
        "ix_fights_report_code",
        "fights",
        ["report_code"],
    )
    op.create_index(
        "ix_fights_encounter_id",
        "fights",
        ["encounter_id"],
    )

    # top_rankings — filtered by (encounter_id, class, spec) in compare/rankings queries
    op.create_index(
        "ix_top_rankings_encounter_class_spec",
        "top_rankings",
        ["encounter_id", "class", "spec"],
    )


def downgrade() -> None:
    op.drop_index("ix_top_rankings_encounter_class_spec", table_name="top_rankings")
    op.drop_index("ix_fights_encounter_id", table_name="fights")
    op.drop_index("ix_fights_report_code", table_name="fights")
    op.drop_index("ix_fight_performances_class_spec", table_name="fight_performances")
    op.drop_index("ix_fight_performances_player_name", table_name="fight_performances")
    op.drop_index("ix_fight_performances_fight_id", table_name="fight_performances")
```

**Step 2: Add matching index declarations to ORM models**

In `code/shukketsu/db/models.py`, add `Index` import and `__table_args__` to the affected models. This keeps the ORM in sync with the migration so future autogenerate migrations don't re-create these indexes.

For `FightPerformance`, add:
```python
from sqlalchemy import Index
# ... existing imports ...

class FightPerformance(Base):
    __tablename__ = "fight_performances"
    __table_args__ = (
        Index("ix_fight_performances_fight_id", "fight_id"),
        Index("ix_fight_performances_player_name", "player_name"),
        Index("ix_fight_performances_class_spec", "player_class", "player_spec"),
    )
    # ... rest of columns unchanged ...
```

For `Fight`, add to existing `__table_args__` tuple (it already has a `UniqueConstraint`):
```python
class Fight(Base):
    __tablename__ = "fights"
    __table_args__ = (
        UniqueConstraint("report_code", "fight_id"),
        Index("ix_fights_report_code", "report_code"),
        Index("ix_fights_encounter_id", "encounter_id"),
    )
```

For `TopRanking`, add:
```python
class TopRanking(Base):
    __tablename__ = "top_rankings"
    __table_args__ = (
        Index("ix_top_rankings_encounter_class_spec", "class", "spec"),
    )
```

Note: The `TopRanking` index uses the column name `"class"` (the actual DB column name, since `class_` is the Python attribute with `mapped_column("class", ...)`).

**Step 3: Run existing tests to verify ORM changes don't break anything**

Run: `pytest code/tests/db/ -v`
Expected: All pass

**Step 4: Run the migration against the dev database**

Run: `cd /home/lyro/nvidia-workbench/wcl-tbc-analyzer/code && alembic upgrade head`
Expected: Migration 003 applied successfully

**Step 5: Commit**

```bash
git add code/alembic/versions/003_add_performance_indexes.py code/shukketsu/db/models.py
git commit -m "perf: add database indexes for fight_performances, fights, and top_rankings"
```

---

## Phase 2: Agent Correctness

### Task 2: Strip think tags inside CRAG graph nodes

The `_strip_think_tags()` function exists in `analyze.py` but the router and grader nodes receive raw model output. Nemotron's `</think>` prefix can cause misclassification.

**Files:**
- Modify: `code/shukketsu/agent/graph.py`
- Modify: `code/tests/agent/test_graph.py`

**Step 1: Write failing tests for think-tag handling in router and grader**

Add to `code/tests/agent/test_graph.py`:

```python
class TestThinkTagHandling:
    async def test_route_strips_think_tags(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="<think>Let me analyze this query type...</think>\nmy_performance"
        )
        state = {
            "messages": [HumanMessage(content="Why is my DPS low?")],
        }
        result = await route_query(state, mock_llm)
        assert result["query_type"] == "my_performance"

    async def test_grade_strips_think_tags(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="<think>The data looks complete...</think>\nrelevant"
        )
        state = {
            "messages": [
                HumanMessage(content="Show my parses"),
                AIMessage(content="DPS: 1500"),
            ],
            "retry_count": 0,
        }
        result = await grade_results(state, mock_llm)
        assert result["grade"] == "relevant"

    async def test_route_strips_think_tags_insufficient(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="<think>Hmm not enough data</think>  insufficient"
        )
        state = {
            "messages": [
                HumanMessage(content="Show parses"),
                AIMessage(content="No data"),
            ],
            "retry_count": 0,
        }
        result = await grade_results(state, mock_llm)
        assert result["grade"] == "insufficient"
```

**Step 2: Run tests to verify they fail**

Run: `pytest code/tests/agent/test_graph.py::TestThinkTagHandling -v`
Expected: FAIL — think tags not stripped, query_type/grade falls back to default

**Step 3: Implement think-tag stripping in graph.py**

Add a `_strip_think_tags` helper at module level in `graph.py` (import the same regex pattern from analyze.py, or define locally to avoid circular import):

```python
import re

_THINK_PATTERN = re.compile(r"^.*?</think>\s*", flags=re.DOTALL)

def _strip_think_tags(text: str) -> str:
    """Strip Nemotron's leaked reasoning/think tags from output."""
    return _THINK_PATTERN.sub("", text)
```

Then modify `route_query`:
```python
async def route_query(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    messages = [
        SystemMessage(content=ROUTER_PROMPT),
        state["messages"][-1],
    ]
    response = await llm.ainvoke(messages)
    query_type = _strip_think_tags(response.content).strip().lower()

    if query_type not in VALID_QUERY_TYPES:
        query_type = "general"

    logger.info("Routed query as: %s", query_type)
    return {"query_type": query_type}
```

And modify `grade_results`:
```python
async def grade_results(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    retry_count = state.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        logger.info("Max retries reached, proceeding to analysis")
        return {"grade": "relevant"}

    recent = state["messages"][-3:] if len(state["messages"]) > 3 else state["messages"]
    messages = [
        SystemMessage(content=GRADER_PROMPT),
        HumanMessage(content=f"User question and retrieved data:\n{_format_messages(recent)}"),
    ]
    response = await llm.ainvoke(messages)
    grade = _strip_think_tags(response.content).strip().lower()

    if grade not in ("relevant", "insufficient"):
        grade = "relevant"

    logger.info("Graded results as: %s", grade)
    return {"grade": grade}
```

**Step 4: Run tests to verify they pass**

Run: `pytest code/tests/agent/test_graph.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add code/shukketsu/agent/graph.py code/tests/agent/test_graph.py
git commit -m "fix: strip think tags in router and grader nodes"
```

---

### Task 3: Normalize tool argument case (PascalCase → snake_case)

Nemotron sometimes generates PascalCase keys for tool arguments. Currently these silently produce `None` values.

**Files:**
- Modify: `code/shukketsu/agent/graph.py`
- Modify: `code/tests/agent/test_graph.py`

**Step 1: Write failing test**

```python
class TestToolArgNormalization:
    def test_normalize_converts_pascal_to_snake(self):
        from shukketsu.agent.graph import _normalize_tool_args
        args = {"EncounterName": "Patchwerk", "PlayerName": "Lyro"}
        result = _normalize_tool_args(args)
        assert result == {"encounter_name": "Patchwerk", "player_name": "Lyro"}

    def test_normalize_preserves_snake_case(self):
        from shukketsu.agent.graph import _normalize_tool_args
        args = {"encounter_name": "Patchwerk", "player_name": "Lyro"}
        result = _normalize_tool_args(args)
        assert result == {"encounter_name": "Patchwerk", "player_name": "Lyro"}

    def test_normalize_handles_mixed_case(self):
        from shukketsu.agent.graph import _normalize_tool_args
        args = {"ClassName": "Warrior", "spec_name": "Arms"}
        result = _normalize_tool_args(args)
        assert result == {"class_name": "Warrior", "spec_name": "Arms"}
```

**Step 2: Run tests to verify they fail**

Run: `pytest code/tests/agent/test_graph.py::TestToolArgNormalization -v`
Expected: FAIL — ImportError, function doesn't exist

**Step 3: Implement case normalization**

Add to `graph.py`:

```python
def _normalize_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    """Convert PascalCase tool argument keys to snake_case.

    Nemotron sometimes generates PascalCase keys (e.g. EncounterName
    instead of encounter_name). This normalizes them.
    """
    normalized = {}
    for key, value in args.items():
        # Convert PascalCase to snake_case: insert _ before uppercase letters
        snake_key = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", key).lower()
        normalized[snake_key] = value
    return normalized
```

Then modify `query_database` to normalize tool call args before they reach the ToolNode:

```python
async def query_database(state: dict[str, Any], llm_with_tools: Any) -> dict[str, Any]:
    query_type = state.get("query_type", "general")
    user_msg = state["messages"][-1] if state["messages"] else HumanMessage(content="")

    system_content = (
        f"{SYSTEM_PROMPT}\n\n"
        f"The user's question has been classified as: {query_type}. "
        f"Use the most appropriate tool(s) to retrieve relevant data."
    )
    messages = [
        SystemMessage(content=system_content),
        user_msg,
    ]
    response = await llm_with_tools.ainvoke(messages)

    # Normalize PascalCase tool args from Nemotron
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            tc["args"] = _normalize_tool_args(tc["args"])

    return {"messages": [response]}
```

**Step 4: Run tests to verify they pass**

Run: `pytest code/tests/agent/test_graph.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add code/shukketsu/agent/graph.py code/tests/agent/test_graph.py
git commit -m "fix: normalize PascalCase tool args from Nemotron to snake_case"
```

---

### Task 4: Remove dead state fields and respond node

The `encounter_context` and `character_context` fields in `AnalyzerState` are never populated. The `respond` (generate_insight) node is a near-noop.

**Files:**
- Modify: `code/shukketsu/agent/state.py`
- Modify: `code/shukketsu/agent/graph.py`
- Modify: `code/tests/agent/test_state.py`
- Modify: `code/tests/agent/test_graph.py`

**Step 1: Read test_state.py to understand existing tests**

Check what tests reference the dead fields.

**Step 2: Remove dead fields from state**

Update `code/shukketsu/agent/state.py`:
```python
from typing import Literal

from langgraph.graph import MessagesState


class AnalyzerState(MessagesState):
    query_type: Literal["my_performance", "comparison", "trend", "general"] | None = None
    grade: str | None = None
    retry_count: int = 0
```

Note: Add `grade` field since `grade_results` returns `{"grade": ...}` and the state needs to carry it for `_should_continue`.

**Step 3: Remove respond node from graph**

In `graph.py`, remove the `generate_insight` function entirely. Update `create_graph`:

```python
def create_graph(llm: Any, tools: list) -> Any:
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    graph = StateGraph(AnalyzerState)

    graph.add_node("route", partial(route_query, llm=llm))
    graph.add_node("query", partial(query_database, llm_with_tools=llm_with_tools))
    graph.add_node("tool_executor", ToolNode(tools) if tools else _noop_tool_node)
    graph.add_node("grade", partial(grade_results, llm=llm))
    graph.add_node("analyze", partial(analyze_results, llm=llm))
    graph.add_node("rewrite", partial(rewrite_query, llm=llm))

    graph.set_entry_point("route")
    graph.add_edge("route", "query")
    graph.add_conditional_edges(
        "query",
        _should_route_to_tools,
        {"tools": "tool_executor", "grade": "grade"},
    )
    graph.add_edge("tool_executor", "grade")
    graph.add_conditional_edges(
        "grade",
        _should_continue,
        {"analyze": "analyze", "rewrite": "rewrite"},
    )
    graph.add_edge("rewrite", "query")
    graph.add_edge("analyze", END)

    return graph.compile()
```

**Step 4: Update tests**

In `test_graph.py`, update `TestCreateGraph.test_graph_has_nodes` — remove assertion for "respond" node. Update any tests that reference `encounter_context` or `character_context`.

In `test_state.py`, remove tests for the dead fields if any exist.

**Step 5: Run tests**

Run: `pytest code/tests/agent/ -v`
Expected: All pass

**Step 6: Commit**

```bash
git add code/shukketsu/agent/state.py code/shukketsu/agent/graph.py code/tests/agent/test_state.py code/tests/agent/test_graph.py
git commit -m "refactor: remove dead respond node and unused state fields"
```

---

### Task 5: Fix deaths query to include players with 0 deaths

The `DEATHS_AND_MECHANICS` query filters `fp.deaths > 0`, missing players with meaningful interrupt/dispel data but 0 deaths.

**Files:**
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/tests/agent/test_tools.py`

**Step 1: Write test for the updated behavior**

Add to `test_tools.py`:
```python
from shukketsu.agent.tools import get_deaths_and_mechanics

class TestGetDeathsAndMechanics:
    async def test_returns_players_with_zero_deaths(self):
        """Tool should return players with interrupts/dispels even if deaths=0."""
        mock_rows = [
            MagicMock(
                player_name="Healer", player_class="Priest", player_spec="Holy",
                deaths=0, interrupts=0, dispels=15,
                encounter_name="Gothik", kill=True, duration_ms=180000,
            ),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.agent.tools._get_session", return_value=mock_session):
            result = await get_deaths_and_mechanics.ainvoke(
                {"encounter_name": "Gothik"}
            )

        assert "Healer" in result
        assert "Disp: 15" in result
```

**Step 2: Update the query**

In `code/shukketsu/db/queries.py`, modify `DEATHS_AND_MECHANICS`:

```python
DEATHS_AND_MECHANICS = text("""
    SELECT fp.player_name, fp.player_class, fp.player_spec,
           fp.deaths, fp.interrupts, fp.dispels,
           e.name AS encounter_name, f.kill, f.duration_ms
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE e.name ILIKE :encounter_name
      AND (fp.deaths > 0 OR fp.interrupts > 0 OR fp.dispels > 0)
    ORDER BY fp.deaths DESC, fp.interrupts DESC, fp.dispels DESC, f.end_time DESC
    LIMIT 20
""")
```

**Step 3: Run tests**

Run: `pytest code/tests/agent/test_tools.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add code/shukketsu/db/queries.py code/tests/agent/test_tools.py
git commit -m "fix: include players with 0 deaths but meaningful interrupt/dispel data"
```

---

## Phase 3: API & LLM Hardening

### Task 6: Add real health check endpoint

**Files:**
- Modify: `code/shukketsu/api/routes/health.py`
- Modify: `code/shukketsu/api/app.py`
- Modify: `code/tests/api/test_health.py`

**Step 1: Write failing tests**

Update `code/tests/api/test_health.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from shukketsu.api.routes.health import router, set_health_deps


class TestHealthEndpoint:
    async def test_healthy_when_db_and_llm_reachable(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        mock_session_factory = AsyncMock()
        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        set_health_deps(session_factory=mock_session_factory, llm_base_url="http://localhost:11434")

        with patch("shukketsu.api.routes.health.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert data["llm"] == "ok"

    async def test_unhealthy_when_db_unreachable(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        mock_session_factory = AsyncMock()
        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session
        mock_session.execute.side_effect = Exception("connection refused")

        set_health_deps(session_factory=mock_session_factory, llm_base_url="http://localhost:11434")

        with patch("shukketsu.api.routes.health.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["database"] == "error"
```

**Step 2: Run tests to verify they fail**

Run: `pytest code/tests/api/test_health.py -v`
Expected: FAIL — `set_health_deps` doesn't exist, response doesn't have `database`/`llm` fields

**Step 3: Implement real health check**

Update `code/shukketsu/api/routes/health.py`:

```python
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()

_session_factory = None
_llm_base_url = None


def set_health_deps(session_factory=None, llm_base_url=None) -> None:
    global _session_factory, _llm_base_url
    _session_factory = session_factory
    _llm_base_url = llm_base_url


@router.get("/health")
async def health():
    db_status = "ok"
    llm_status = "ok"
    healthy = True

    # Check database
    if _session_factory:
        session = _session_factory()
        try:
            await session.execute(text("SELECT 1"))
        except Exception as e:
            logger.warning("Health check: DB unreachable: %s", e)
            db_status = "error"
            healthy = False
        finally:
            await session.close()
    else:
        db_status = "not configured"

    # Check LLM
    if _llm_base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{_llm_base_url}/models")
                if resp.status_code != 200:
                    llm_status = "error"
                    healthy = False
        except Exception as e:
            logger.warning("Health check: LLM unreachable: %s", e)
            llm_status = "error"
            healthy = False
    else:
        llm_status = "not configured"

    body = {
        "status": "ok" if healthy else "degraded",
        "version": "0.1.0",
        "database": db_status,
        "llm": llm_status,
    }
    status_code = 200 if healthy else 503
    return JSONResponse(content=body, status_code=status_code)
```

**Step 4: Wire health deps in app lifespan**

In `code/shukketsu/api/app.py`, add to the lifespan after creating session_factory and llm:

```python
from shukketsu.api.routes.health import set_health_deps
# ... inside lifespan, after setting up session_factory and llm:
set_health_deps(session_factory=session_factory, llm_base_url=settings.llm.base_url)
```

**Step 5: Run tests**

Run: `pytest code/tests/api/test_health.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add code/shukketsu/api/routes/health.py code/shukketsu/api/app.py code/tests/api/test_health.py
git commit -m "feat: add real health check with DB and LLM connectivity checks"
```

---

### Task 7: Add max_tokens and timeout to LLM client

**Files:**
- Modify: `code/shukketsu/config.py`
- Modify: `code/shukketsu/agent/llm.py`
- Modify: `code/tests/agent/test_llm.py`

**Step 1: Write failing test**

Add to `code/tests/agent/test_llm.py`:

```python
class TestLLMConfig:
    def test_llm_has_max_tokens(self):
        # ... create settings, create_llm, check max_tokens is set
        pass

    def test_llm_has_timeout(self):
        # ... create settings, create_llm, check timeout is set
        pass
```

The exact test shape depends on the existing `test_llm.py` — read it first.

**Step 2: Add config fields**

In `code/shukketsu/config.py`, update `LLMConfig`:

```python
class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    model: str = "nemotron-3-nano:30b"
    api_key: str = "ollama"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 300
```

**Step 3: Pass to LLM client**

In `code/shukketsu/agent/llm.py`:

```python
def create_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm.model,
        base_url=settings.llm.base_url,
        api_key=settings.llm.api_key,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
    )
```

**Step 4: Run tests**

Run: `pytest code/tests/ -v -k "llm or config"`
Expected: All pass

**Step 5: Commit**

```bash
git add code/shukketsu/config.py code/shukketsu/agent/llm.py code/tests/agent/test_llm.py
git commit -m "feat: add max_tokens and timeout configuration for LLM client"
```

---

### Task 8: Add batch deaths endpoint for roster page

The RosterPage makes N+1 sequential API calls for death accountability. Add a batch endpoint.

**Files:**
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/shukketsu/api/models.py`
- Modify: `code/shukketsu/api/routes/data.py`

**Step 1: Add the batch query**

Add to `code/shukketsu/db/queries.py`:

```python
REPORT_DEATHS = text("""
    SELECT f.fight_id, e.name AS encounter_name,
           fp.player_name, fp.player_class, fp.player_spec,
           fp.deaths, fp.interrupts, fp.dispels
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND fp.deaths > 0
    ORDER BY f.fight_id ASC, fp.deaths DESC
""")
```

**Step 2: Add response model**

Add to `code/shukketsu/api/models.py`:

```python
class DeathEntry(BaseModel):
    fight_id: int
    encounter_name: str
    player_name: str
    player_class: str
    player_spec: str
    deaths: int
    interrupts: int
    dispels: int
```

**Step 3: Add endpoint**

Add to `code/shukketsu/api/routes/data.py`:

```python
@router.get("/reports/{report_code}/deaths", response_model=list[DeathEntry])
async def report_deaths(report_code: str):
    session = await _get_session()
    try:
        result = await session.execute(q.REPORT_DEATHS, {"report_code": report_code})
        rows = result.fetchall()
        return [DeathEntry(**dict(r._mapping)) for r in rows]
    except Exception as e:
        logger.exception("Failed to get death data")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        await session.close()
```

**Step 4: Run tests**

Run: `pytest code/tests/ -v`
Expected: All pass (no breaking changes)

**Step 5: Commit**

```bash
git add code/shukketsu/db/queries.py code/shukketsu/api/models.py code/shukketsu/api/routes/data.py
git commit -m "feat: add batch deaths endpoint to eliminate N+1 queries on roster page"
```

---

## Phase 4: Dead Code Cleanup

### Task 9: Remove dead code

**Files:**
- Modify: `code/shukketsu/pipeline/normalize.py`
- Modify: `code/shukketsu/wcl/queries.py`
- Modify: `code/tests/pipeline/test_normalize.py` (if tests exist for dead functions)

**Step 1: Check what tests reference the dead code**

Read `code/tests/pipeline/test_normalize.py` to see if `compute_dps`/`compute_hps` are tested. If so, remove those tests.

**Step 2: Remove `compute_dps` and `compute_hps` from normalize.py**

These functions are unused — DPS values come directly from WCL. Keep `is_boss_fight` which is used.

Update `code/shukketsu/pipeline/normalize.py`:
```python
from typing import Any


def is_boss_fight(fight_data: dict[str, Any]) -> bool:
    return fight_data.get("encounterID", 0) > 0
```

**Step 3: Remove unused queries from wcl/queries.py**

Remove `CHARACTER_RANKINGS` and `REPORT_EVENTS` — these are never imported by any pipeline module.

Also remove `RATE_LIMIT_FRAGMENT` — it's never used (all queries use inline `RATE_LIMIT` placeholder).

**Step 4: Verify no imports reference the removed code**

Run: `grep -r "compute_dps\|compute_hps\|CHARACTER_RANKINGS\|REPORT_EVENTS\|RATE_LIMIT_FRAGMENT" code/shukketsu/`
Expected: No results (other than the files being modified)

**Step 5: Run tests**

Run: `pytest code/tests/ -v`
Expected: All pass

**Step 6: Commit**

```bash
git add code/shukketsu/pipeline/normalize.py code/shukketsu/wcl/queries.py
# Also add any modified test files
git commit -m "chore: remove dead code (compute_dps/hps, unused WCL queries)"
```

---

## Phase 5: Remaining Improvements

### Task 10: Add `grade` field to AnalyzerState properly

This was partially covered in Task 4 but needs its own verification. The `_should_continue` function reads `state.get("grade")` but `grade` is not a declared field on `AnalyzerState`. This works because LangGraph states are dicts, but it should be explicit.

**Already handled in Task 4** — verify the `grade` field was added to the state class.

---

### Task 11: Update CLAUDE.md with resolved issues

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add resolved issues**

Add to the "Resolved issues" section in CLAUDE.md:

```markdown
- **Missing indexes:** Migration 003 adds indexes on `fight_performances(fight_id, player_name, class+spec)`, `fights(report_code, encounter_id)`, and `top_rankings(encounter_id, class, spec)`.
- **Think tags in agent nodes:** `_strip_think_tags()` now applied in both `route_query` and `grade_results` graph nodes, not just the API response.
- **Tool arg case normalization:** `_normalize_tool_args()` in `graph.py` converts Nemotron's PascalCase tool argument keys to snake_case.
- **Dead respond node:** Removed the near-noop `generate_insight` node; `analyze` now flows directly to END.
- **Deaths query:** `DEATHS_AND_MECHANICS` now includes players with `deaths=0` who have interrupt/dispel contributions.
- **Health check:** `/health` endpoint now pings the database (`SELECT 1`) and LLM (`/v1/models`) and returns 503 when either is unreachable.
- **LLM guardrails:** `max_tokens` (4096) and `timeout` (300s) now configured on the ChatOpenAI client.
- **Batch deaths endpoint:** `GET /api/data/reports/{code}/deaths` replaces N+1 per-fight queries on the roster page.
- **Dead code removed:** `compute_dps`/`compute_hps` (unused), `CHARACTER_RANKINGS`/`REPORT_EVENTS`/`RATE_LIMIT_FRAGMENT` (unused WCL queries).
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with resolved issues from improvement sweep"
```

---

## Execution Order

Tasks can be parallelized in groups:

**Group A (independent):** Tasks 1, 2, 3, 5, 7, 8, 9
**Group B (depends on Task 4 completing):** Task 4 then verify Task 10
**Group C (after all):** Task 6 (health check touches app.py lifespan), Task 11

Recommended serial order for a single executor: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 11

---

## Verification

After all tasks complete:

```bash
pytest code/tests/ -v
ruff check code/
```

All tests should pass. No lint errors.
