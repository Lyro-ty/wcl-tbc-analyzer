# CRAG → ReAct Agent Simplification

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 6-node CRAG state graph with a minimal 2-node ReAct loop. Fewer LLM calls per request, same analysis quality, simpler code.

**Architecture:** Hand-rolled ReAct graph using `StateGraph` + `tools_condition` from `langgraph.prebuilt`. Two nodes: `agent` (LLM with tools) and `tools` (ToolNode). The agent loops until it responds without tool calls.

**Tech Stack:** Python 3.12, LangGraph, langchain-openai, FastAPI, pytest

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Graph approach | Hand-rolled 2-node ReAct | Simpler than CRAG, gives PascalCase normalization hook |
| `query_type` | Drop entirely | Decorative — routing added one sentence to system prompt, frontend doesn't use it |
| Streaming | Stream only final response | Filter for agent node, skip tool_call_chunks, reset think-tag buffer between turns |
| Max iterations | `recursion_limit=25` (default) | ~12 tool-calling rounds, plenty for 30 tools. User wants LLM freedom |
| System prompt | Merge SYSTEM_PROMPT + ANALYSIS_PROMPT | Single prompt for the agent — no separate analyze step |

---

## Architecture Change

```
CRAG (current, 6 nodes, 4+ LLM calls):
  route → query → tool_executor → grade → analyze → END
                                    ↓
                            rewrite → query (retry loop)

ReAct (new, 2 nodes, 2+ LLM calls):
  agent ⇄ tools → END
  (LLM decides when to call tools and when to respond)
```

### What gets deleted
- `route_query()` node + `ROUTER_PROMPT` — classification was decorative
- `grade_results()` node + `GRADER_PROMPT` — grader almost always said "relevant"
- `rewrite_query()` node + `REWRITE_PROMPT` — rewrite rarely recovered
- `analyze_results()` node — the ReAct agent's final response IS the analysis
- `AnalyzerState.query_type`, `grade`, `retry_count` fields
- `_should_continue()`, `_should_route_to_tools()` conditional edge functions
- `_format_messages()` helper (was only for grader)
- `_noop_tool_node()` placeholder
- `MAX_RETRIES` constant
- `VALID_QUERY_TYPES` constant

### What stays
- `_normalize_tool_args()` — still needed for Nemotron's PascalCase quirk
- Think-tag stripping — stays in `analyze.py` (API layer), not in graph
- `ToolNode` — used by the graph's `tools` node
- All 30 agent tools — completely unchanged
- `@db_tool` decorator and session wiring — unchanged

---

## Task 1: Rewrite `graph.py` (core change)

Replace the entire CRAG graph with a minimal ReAct loop.

**File:** `code/shukketsu/agent/graph.py`

**New implementation (~50 lines, down from ~206):**

```python
"""LangGraph ReAct agent for raid analysis."""

import logging
import re
from functools import partial
from typing import Any

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState

logger = logging.getLogger(__name__)


def _normalize_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    """Convert PascalCase tool argument keys to snake_case.

    Nemotron sometimes generates PascalCase keys (e.g. EncounterName
    instead of encounter_name). This normalizes them.
    """
    normalized = {}
    for key, value in args.items():
        snake_key = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", key).lower()
        normalized[snake_key] = value
    return normalized


async def agent_node(state: dict[str, Any], llm_with_tools: Any) -> dict[str, Any]:
    """Invoke the LLM with tools. Normalizes PascalCase tool args."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)

    # Normalize PascalCase tool args from Nemotron
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            tc["args"] = _normalize_tool_args(tc["args"])

    return {"messages": [response]}


def create_graph(llm: Any, tools: list) -> CompiledStateGraph:
    """Create and compile the ReAct agent graph."""
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    graph = StateGraph(AnalyzerState)

    graph.add_node("agent", partial(agent_node, llm_with_tools=llm_with_tools))
    graph.add_node("tools", ToolNode(tools) if tools else _noop_tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


async def _noop_tool_node(state: dict[str, Any]) -> dict[str, Any]:
    """Placeholder when no tools are configured."""
    return {}
```

Note: needs `from functools import partial` import added.

---

## Task 2: Simplify `state.py`

Remove CRAG-specific fields from the state.

**File:** `code/shukketsu/agent/state.py`

**Before:**
```python
class AnalyzerState(MessagesState):
    query_type: Literal["my_performance", "comparison", "trend", "rotation", "general"] | None = None
    grade: str | None = None
    retry_count: int = 0
```

**After:**
```python
class AnalyzerState(MessagesState):
    pass
```

Keep `AnalyzerState` as a class (not just alias `MessagesState`) so we can add fields later without changing imports everywhere.

---

## Task 3: Merge prompts in `prompts.py`

Delete `ROUTER_PROMPT`, `GRADER_PROMPT`, `REWRITE_PROMPT`. Merge `SYSTEM_PROMPT` and `ANALYSIS_PROMPT` into a single `SYSTEM_PROMPT`. Add workflow guidance for multi-tool chaining.

**File:** `code/shukketsu/agent/prompts.py`

**Delete:**
- `ROUTER_PROMPT` (lines 165-182)
- `GRADER_PROMPT` (lines 153-163)
- `REWRITE_PROMPT` (lines 184-188)

**Merge ANALYSIS_PROMPT into SYSTEM_PROMPT**, appending it after the current system prompt content.

**Add workflow guidance section** (new, appended to the merged prompt):

```python
"""
## Workflow Patterns

For thorough analysis, chain multiple tools. Common patterns:

- **Full performance review**: resolve_my_fights → get_my_performance →
  get_spec_benchmark → get_ability_breakdown → get_activity_report →
  get_cooldown_efficiency → respond with analysis

- **Raid comparison**: get_raid_execution → compare_raid_to_top →
  get_encounter_benchmarks → respond with analysis

- **Progression check**: get_progression → get_regressions →
  get_my_performance (bests_only=True) → respond with analysis

- **Gear/prep audit**: get_enchant_gem_check → get_consumable_check →
  get_gear_changes → respond with analysis

Retrieve all relevant data BEFORE writing your analysis. Call multiple
tools if needed — don't stop after one tool call if more data would
improve your answer.
"""
```

**Important rewording:** The current ANALYSIS_PROMPT says "Based on the retrieved
raid performance data, provide a thorough analysis." This is phrased for a separate
step that receives pre-fetched data. In ReAct, the same LLM both fetches and analyzes.
Reword to: "When you have gathered sufficient data using the tools above, structure
your final response as follows:" — this ensures the LLM calls tools before composing
its analysis rather than responding immediately.

The final `SYSTEM_PROMPT` structure:
1. Identity + domain knowledge (existing)
2. Tool descriptions (existing)
3. Context resolution (existing)
4. Role awareness (existing)
5. TBC game mechanics (existing)
6. Analysis framework (moved from ANALYSIS_PROMPT, reworded for ReAct)
7. Structured response format (moved from ANALYSIS_PROMPT)
8. Workflow patterns (new)

---

## Task 4: Update `analyze.py` (API layer)

**File:** `code/shukketsu/api/routes/analyze.py`

### 4a: Drop `query_type` from response model

```python
# Before
class AnalyzeResponse(BaseModel):
    answer: str
    query_type: str | None = None

# After
class AnalyzeResponse(BaseModel):
    answer: str
```

### 4b: Simplify non-streaming endpoint

Remove `query_type` from the return:

```python
return AnalyzeResponse(answer=answer)
```

### 4c: Update streaming filter

Change node filter from `"analyze"` to `"agent"`, skip tool_call_chunks, and
**reset think-tag buffer between agent turns**.

With CRAG, the "analyze" node fired once so buffer state was simple. With ReAct,
the "agent" node fires multiple times (once per tool-calling round + final response).
If `think_done=True` from the first agent call, subsequent agent calls would stream
content unfiltered — leaking intermediate reasoning.

Fix: reset buffer state when we see the "tools" node (indicating a new agent turn follows).

```python
# In event_generator():
buffer = ""
think_done = False

async for chunk, metadata in graph.astream(..., stream_mode="messages"):
    node = metadata.get("langgraph_node") if isinstance(metadata, dict) else None

    # Reset think-tag buffer between agent turns
    if node == "tools":
        buffer = ""
        think_done = False
        continue

    if node != "agent":
        continue

    if not hasattr(chunk, "content") or not chunk.content:
        continue

    # Skip tool call chunks (use tool_call_chunks, not tool_calls, for streaming)
    if getattr(chunk, "tool_call_chunks", None):
        continue

    token = chunk.content
    # ... think-tag buffering as before ...
```

**Why this works:** Nemotron always produces `<think>...</think>` before content.
The think-tag buffer delays streaming until after `</think>`. By that point,
`tool_call_chunks` have arrived if it's a tool-calling turn → nothing leaks.
For the final turn (no tools), content after `</think>` streams normally.

### 4d: Drop `query_type` from SSE done event

```python
# Before
yield {"data": json.dumps({"done": True, "query_type": query_type})}

# After
yield {"data": json.dumps({"done": True})}
```

Remove the `query_type` tracking variable from `event_generator()`.

### 4e: Clean up imports

Remove `GRADER_PROMPT`, `REWRITE_PROMPT`, `ROUTER_PROMPT`, `ANALYSIS_PROMPT` if they were imported (they aren't currently imported in analyze.py, but verify).

---

## Task 5: Update frontend (minimal)

**File:** `code/frontend/src/pages/ChatPage.tsx` (or wherever SSE is consumed)

Remove any handling of `query_type` from the SSE `done` event. If the frontend displays `query_type`, remove that UI element.

Check `code/frontend/src/lib/types.ts` for any `query_type` field in response types.

---

## Task 6: Rewrite graph tests

**File:** `code/tests/agent/test_graph.py` (230 lines → ~120 lines)

### Delete (CRAG-specific tests):
- `TestRouteQuery` — all 4 tests (no router)
- `TestGradeResults` — all 3 tests (no grader)
- `TestFormatMessages` — all 2 tests (no grader formatting)
- `TestMaxRetries` — 1 test (no retry mechanism)
- Any tests for `_should_continue`, `_should_route_to_tools`

### Keep/modify:
- `TestCreateGraph` — verify graph compiles, has "agent" and "tools" nodes
- `TestToolArgNormalization` — PascalCase normalization unchanged

### Add new tests:
- `test_agent_node_calls_tools` — LLM responds with tool_calls → tools node executes
- `test_agent_node_responds_without_tools` — LLM responds with content only → END
- `test_agent_node_normalizes_tool_args` — PascalCase → snake_case in agent_node
- `test_system_prompt_in_messages` — agent_node prepends SystemMessage
- `test_graph_has_two_nodes` — "agent" and "tools" only
- `test_tools_condition_routes_correctly` — tool_calls → "tools", no tool_calls → END

---

## Task 7: Update analyze route tests

**File:** `code/tests/api/test_analyze.py` (495 lines → ~470 lines)

### Modify:
- Remove `query_type` assertions from `test_analyze_returns_analysis` and similar
- Change `langgraph_node: "analyze"` to `langgraph_node: "agent"` in streaming mock metadata
- Remove `query_type` from SSE done event assertions
- Remove `query_type` tracking variable from streaming tests

### Keep unchanged:
- Think-tag stripping tests
- Semaphore tests
- Langfuse callback tests
- Error handling tests
- Buffer limit tests

---

## Task 8: Simplify state tests

**File:** `code/tests/agent/test_state.py` (59 lines → ~30 lines)

Remove tests for `query_type`, `grade`, `retry_count` fields. Keep basic `AnalyzerState` instantiation and message handling tests.

---

## Task 9: Update CLAUDE.md

Update documentation to reflect the new architecture:
- Change CRAG flow diagram to ReAct
- Remove references to router, grader, rewrite nodes
- Update node count (6 → 2)
- Remove `query_type` from API response docs
- Update graph.py description
- Remove `MAX_RETRIES` references

---

## Task 10: Run full test suite + lint

```bash
python3 -m pytest code/tests/ -v --timeout=30
python3 -m ruff check code/
```

Verify all tests pass and no lint errors.

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Nemotron doesn't chain tools well in ReAct mode | Workflow patterns in system prompt guide multi-tool usage |
| Streaming breaks with new node filter | Reset think-tag buffer between agent turns; think-tag buffering acts as natural delay to prevent intermediate content leaking |
| LLM loops infinitely calling tools | `recursion_limit=25` in graph config (default) |
| Frontend breaks without `query_type` | Verify frontend handles missing field gracefully |
| Tool arg normalization misses edge cases | Existing `_normalize_tool_args` unchanged, just moved to agent_node |

## Files Changed Summary

| File | Action | Lines |
|------|--------|-------|
| `code/shukketsu/agent/graph.py` | Rewrite | 206 → ~50 |
| `code/shukketsu/agent/state.py` | Simplify | 12 → ~6 |
| `code/shukketsu/agent/prompts.py` | Merge + delete 3 prompts | 253 → ~180 |
| `code/shukketsu/api/routes/analyze.py` | Modify | ~15 lines changed |
| `code/frontend/src/` | Minor | Remove `query_type` handling |
| `code/tests/agent/test_graph.py` | Rewrite | 230 → ~120 |
| `code/tests/api/test_analyze.py` | Modify | ~25 lines changed |
| `code/tests/agent/test_state.py` | Simplify | 59 → ~30 |
| `CLAUDE.md` | Update | Docs only |

**Net reduction:** ~250 lines of production code, ~100 lines of tests
