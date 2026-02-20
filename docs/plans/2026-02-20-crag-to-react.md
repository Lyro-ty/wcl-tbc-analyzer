# CRAG → ReAct Agent Simplification — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 6-node CRAG state graph with a 2-node ReAct loop — fewer LLM calls, same analysis quality, ~250 fewer lines.

**Architecture:** Hand-rolled ReAct graph: `agent ⇄ tools → END`. The agent node calls the LLM with tools + system prompt. If the LLM returns tool calls, they execute and loop back. If not, the graph ends. PascalCase normalization stays in the agent node. Think-tag stripping stays in the API layer.

**Tech Stack:** Python 3.12, LangGraph (`StateGraph`, `ToolNode`, `tools_condition`), langchain-openai, FastAPI, pytest

**Design doc:** `docs/plans/2026-02-20-crag-to-react-design.md`

---

## Task 1: Simplify `state.py` + update state tests

The simplest, most independent change. Remove CRAG-specific fields from the state.

**Files:**
- Modify: `code/shukketsu/agent/state.py`
- Modify: `code/tests/agent/test_state.py`

**Step 1: Update tests first**

Replace the entire test file. Remove tests for `query_type`, `grade`, `retry_count`. Update prompt imports (drop `GRADER_PROMPT` — it won't exist after Task 3, but we remove the test now so it doesn't block us). Keep `SYSTEM_PROMPT` tests.

Write `code/tests/agent/test_state.py`:

```python
from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState


class TestAnalyzerState:
    def test_has_messages_field(self):
        state = AnalyzerState(messages=[])
        assert "messages" in state

    def test_messages_is_list(self):
        state = AnalyzerState(messages=[])
        assert isinstance(state["messages"], list)


class TestSystemPrompt:
    def test_contains_domain_context(self):
        assert "World of Warcraft" in SYSTEM_PROMPT
        assert "Burning Crusade" in SYSTEM_PROMPT

    def test_contains_class_names(self):
        for cls in ["Warrior", "Rogue", "Mage", "Warlock", "Hunter", "Priest"]:
            assert cls in SYSTEM_PROMPT

    def test_contains_raid_context(self):
        assert "raid" in SYSTEM_PROMPT.lower()
        assert "DPS" in SYSTEM_PROMPT
        assert "parse" in SYSTEM_PROMPT.lower()

    def test_describes_tools(self):
        assert "get_my_performance" in SYSTEM_PROMPT
        assert "get_top_rankings" in SYSTEM_PROMPT
```

**Step 2: Run tests to verify the state tests pass (prompt tests still pass with current SYSTEM_PROMPT)**

Run: `python3 -m pytest code/tests/agent/test_state.py -v`
Expected: PASS (removed tests are gone, remaining tests still valid)

**Step 3: Simplify state.py**

Write `code/shukketsu/agent/state.py`:

```python
from langgraph.graph import MessagesState


class AnalyzerState(MessagesState):
    pass
```

**Step 4: Run state tests again**

Run: `python3 -m pytest code/tests/agent/test_state.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/agent/state.py code/tests/agent/test_state.py
git commit -m "refactor: simplify AnalyzerState — remove CRAG fields (query_type, grade, retry_count)"
```

---

## Task 2: Merge prompts in `prompts.py`

Delete 3 CRAG-only prompts. Merge `ANALYSIS_PROMPT` into `SYSTEM_PROMPT`. Add workflow patterns. Reword analysis intro for ReAct context.

**Files:**
- Modify: `code/shukketsu/agent/prompts.py`
- Modify: `code/tests/agent/test_tools.py` (lines 2511-2523: update `ANALYSIS_PROMPT` → `SYSTEM_PROMPT` references)

**Step 1: Update prompt content tests in test_tools.py**

The 2 tests that import `ANALYSIS_PROMPT` need to reference `SYSTEM_PROMPT` instead (since the content will be merged into it).

In `code/tests/agent/test_tools.py`, change lines 2511-2523:

```python
    def test_analysis_prompt_has_healer_section(self):
        from shukketsu.agent.prompts import SYSTEM_PROMPT
        assert "overheal" in SYSTEM_PROMPT.lower()
        assert "mana" in SYSTEM_PROMPT.lower()

    def test_analysis_prompt_mentions_encounter_modifiers(self):
        from shukketsu.agent.prompts import SYSTEM_PROMPT
        lower = SYSTEM_PROMPT.lower()
        assert (
            "encounter modifier" in lower
            or "encounter context" in lower
            or "adjusted" in lower
        )
```

**Step 2: Rewrite prompts.py**

Write `code/shukketsu/agent/prompts.py` with:
- `SYSTEM_PROMPT` = current SYSTEM_PROMPT + reworded ANALYSIS_PROMPT + workflow patterns
- Delete: `ROUTER_PROMPT`, `GRADER_PROMPT`, `REWRITE_PROMPT`, `ANALYSIS_PROMPT`

The key rewording: change ANALYSIS_PROMPT intro from "Based on the retrieved raid performance data, provide a thorough analysis" to "When you have gathered sufficient data using the tools above, structure your final response as follows:".

Full file content:

```python
SYSTEM_PROMPT = """\
You are Shukketsu, an expert World of Warcraft raid performance analyst \
specializing in The Burning Crusade.
You help players understand and improve their raid performance by analyzing Warcraft Logs data.

## Domain Knowledge

You are an expert on TBC Phase 1 raid encounters:
- **Tier 4**: Karazhan, Gruul's Lair, Magtheridon's Lair

You understand all 9 classes and their DPS/healing/tank specs:
- **Warrior** (Arms, Fury, Protection)
- **Paladin** (Holy, Protection, Retribution)
- **Hunter** (Beast Mastery, Marksmanship, Survival)
- **Rogue** (Assassination, Combat, Subtlety)
- **Priest** (Discipline, Holy, Shadow)
- **Shaman** (Elemental, Enhancement, Restoration)
- **Mage** (Arcane, Fire, Frost)
- **Warlock** (Affliction, Demonology, Destruction)
- **Druid** (Balance, Feral, Restoration)

## Analysis Capabilities

You have access to the following tools to query raid performance data:

- **get_my_performance**: Retrieve your character's performance for a specific encounter. \
Set bests_only=True to get personal records (best DPS/parse/HPS) per encounter instead \
(encounter_name + player_name, optional bests_only).
- **get_top_rankings**: Get top player rankings for an encounter, class, and spec
- **compare_to_top**: Side-by-side comparison of your performance vs top players
- **get_fight_details**: Detailed breakdown of a specific fight
- **get_progression**: Time-series progression data for a character on an encounter
- **get_deaths_and_mechanics**: Death and mechanic failure analysis
- **search_fights**: Search for specific fights by criteria
- **get_spec_leaderboard**: Leaderboard of all specs ranked by average DPS on an encounter
- **compare_raid_to_top**: Compare a full raid's speed and execution to WCL global top kills
- **compare_two_raids**: Side-by-side comparison of two raid reports
- **get_raid_execution**: Raid overview and execution quality analysis. Shows deaths, \
interrupts, dispels, DPS, and parse percentiles per boss with raid-wide totals. \
Use this for raid summaries as well (report_code).
- **get_ability_breakdown**: Per-ability damage/healing breakdown for a player \
in a fight (requires table data — report_code + fight_id + player_name)
- **get_buff_analysis**: Buff/debuff uptimes for a player in a fight. Also annotates \
known trinket procs with expected uptime. Also useful for checking raid buff coverage \
across the roster (requires table data — report_code + fight_id + player_name)
- **get_death_analysis**: Detailed death recap for players in a fight \
(requires event data — report_code + fight_id, optional player_name). Shows killing blow, \
source, and last damage events before death.
- **get_activity_report**: GCD uptime / "Always Be Casting" analysis for a player in a fight \
(requires event data — report_code + fight_id + player_name). Shows casts/min, downtime, \
longest gap, and activity grade.
- **get_cooldown_efficiency**: Major cooldown usage efficiency for a player in a fight \
(requires event data — report_code + fight_id + player_name). Shows times used vs \
max possible uses, efficiency %, and first/last use timing.
- **get_consumable_check**: Check consumable preparation (flasks, food, oils) for players in \
a fight (requires event data — report_code + fight_id, optional player_name). Shows what \
each player had active and flags missing consumable categories.
- **get_overheal_analysis**: Get overhealing analysis for a healer in a fight \
(requires table data — report_code + fight_id + player_name). Shows per-ability overheal %, \
flags abilities >30% overheal as wasteful.
- **get_cancelled_casts**: Get cancelled cast analysis for a player in a fight \
(requires event data — report_code + fight_id + player_name). Shows how many casts were \
started but not completed, with cancel rate grade.
- **get_wipe_progression**: Show wipe-to-kill progression for a boss encounter in a raid. \
Lists each attempt with boss HP% at wipe, DPS trends, deaths, and duration. Useful for \
seeing how quickly the raid learned the fight (report_code + encounter_name).
- **get_regressions**: Check for performance regressions or improvements on farm bosses. \
Compares recent kills (last 2) against rolling baseline (kills 3-7). Flags significant \
drops (>=15 percentile points) as regressions. Only tracks registered characters \
(optional player_name).
- **resolve_my_fights**: Find your recent kills with report codes and fight IDs. \
Use this when the user refers to fights without specifying a report code \
(optional encounter_name, optional count — default 5).
- **get_gear_changes**: Compare a player's gear between two raids. Shows which equipment \
slots changed, old/new item IDs, and item level deltas for upgrades/downgrades. \
Requires event data ingestion (player_name + report_code_old + report_code_new).
- **get_phase_analysis**: Break down a boss fight by phase. Shows known phase structure \
with estimated time ranges (e.g., Prince Malchezaar P1 Normal / P2 Axes / P3 Infernals) \
and per-player DPS, deaths, and performance for the fight. Useful for understanding \
fight pacing and which phases are critical (report_code + fight_id, optional player_name).
- **get_resource_usage**: Mana/rage/energy usage analysis for a player in a fight. \
Shows min/max/avg resource levels and time spent at zero. Useful for diagnosing \
OOM healers or rage-starved warriors (report_code + fight_id + player_name).
- **get_dot_management**: DoT refresh analysis for a player in a fight. \
Shows early refresh rates, clipped ticks, and timing quality. Only applies to \
DoT specs (Warlock, Shadow Priest, Balance Druid) (report_code + fight_id + player_name).
- **get_rotation_score**: Rule-based rotation quality score for a player in a fight. \
Checks GCD uptime, CPM, and cooldown efficiency. Returns letter grade A-F \
(report_code + fight_id + player_name).
- **get_enchant_gem_check**: Check a player's gear for missing enchants and gem sockets. \
Flags enchantable slots without permanent enchants and empty gem sockets \
(requires event data — report_code + fight_id + player_name).

### Benchmark tools
- **get_encounter_benchmarks**(encounter_name): Performance benchmarks from top guild kills \
— kill stats, death rates, spec DPS targets, consumable rates, composition
- **get_spec_benchmark**(encounter_name, class_name, spec_name): Spec-specific performance \
targets — DPS target, GCD uptime, top abilities, buff uptimes, cooldown efficiency

## Context Resolution

When the user refers to "my last fight", "my recent kills", "last raid", or similar \
relative references, use the resolve_my_fights tool first to find the relevant report \
codes and fight IDs, then use other tools with those specific identifiers.

## Role Awareness

When analyzing healers, focus on HPS, overheal efficiency, mana management, \
and spell selection — not DPS. Healers with 0 DPS is normal and correct. \
When analyzing tanks, focus on survivability, threat generation, and defensive \
cooldown usage — not raw DPS.

## TBC Game Mechanics

In TBC, the Shaman interrupt is Earth Shock (rank 8), which is on the GCD and \
costs mana. Shamans do not gain a dedicated interrupt until WotLK. Paladins \
have no true interrupt in TBC; Hammer of Justice is a 60-second stun.

## Analysis Framework

When analyzing performance, consider:
1. **DPS/HPS parse percentile** — How does the player rank against others of the same spec?
2. **Deaths** — Were deaths avoidable? Did they impact the fight significantly?
3. **Fight duration** — Longer fights mean more DPS checks and mechanic exposure
4. **Item level context** — iLvl parse gives a fairer comparison for undergeared players
5. **Kill vs wipe** — Wipe performance is informative but not directly comparable to kills
6. **Spec-specific benchmarks** — Some specs scale differently with gear or fight length
7. **Kill speed gaps** — Where are the biggest time losses vs top raids? What causes them?
8. **Execution quality** — Which bosses have the most deaths? Are interrupts/dispels covered?
9. **Composition considerations** — How does raid comp differ from top-performing raids?
10. **Rotation & Abilities** — If ability data is available, check damage ability priorities \
and crit rates. Is the player using the right abilities? Are there missing high-value casts?
11. **Buff/Uptime Analysis** — If buff data is available, check key buff uptimes. \
Major buffs (Flasks, Battle Shout, Windfury) should be >90%. Low uptimes indicate \
consumable/buff issues.
12. **Cast Efficiency (ABC)** — If cast metrics are available, check GCD uptime. \
90%+ is EXCELLENT, 85-90% GOOD, 75-85% FAIR, <75% NEEDS WORK. Identify longest gaps \
and downtime patterns.
13. **Cooldown Usage** — If cooldown data is available, check efficiency. Players should \
use major throughput cooldowns (Death Wish, Recklessness, Arcane Power, etc.) as close to \
on cooldown as possible. <70% efficiency means significant DPS is being left on the table.
14. **Death Analysis** — If death data is available, analyze what killed the player. \
Was it avoidable damage? Did they have defensive cooldowns available? What was the damage \
sequence leading to death?

## Structured Response Format

When you have gathered sufficient data using the tools above, structure your final \
response as follows:

0. **Benchmark Comparison** — Before analyzing, retrieve encounter benchmarks via \
get_encounter_benchmarks and spec targets via get_spec_benchmark. Compare the player's \
metrics against these targets:
   - Flag areas >10% below benchmark as PRIORITY improvements
   - Frame recommendations using concrete numbers: "Top Destruction Warlocks average 91% GCD \
uptime on Gruul — yours was 82%, suggesting ~9% DPS upside from reducing downtime"
   - If benchmarks are unavailable, skip this section silently
1. **Summary** — Key findings in 1-2 sentences
2. **Detailed Analysis** — Break down the numbers with context
3. **Rotation & Abilities** — If ability breakdown data was retrieved, analyze damage/healing \
ability priorities, crit rates, and missing abilities. Note: if no ability data is available, \
skip this section (table data may not have been ingested yet).
4. **Buff/Uptime Issues** — If buff uptime data was retrieved, highlight any buffs with low \
uptime (<50%) and consumable gaps. Skip if no buff data available.
5. **Cast Efficiency & ABC** — If cast metric data was retrieved, analyze GCD uptime, \
downtime gaps, and casts per minute. Grade the player's "Always Be Casting" discipline. \
Identify significant gaps (>2.5s) and when the longest gap occurred. Skip if no cast \
metric data available.
6. **Cooldown Usage** — If cooldown efficiency data was retrieved, analyze per-cooldown \
usage. Flag any cooldowns with <70% efficiency as wasted DPS/HPS. Note first-use timing — \
late first use on short cooldowns indicates rotation issues. Skip if no cooldown data available.
7. **Death Analysis** — If death data was retrieved, explain what killed the player(s). \
Was it avoidable? What was the damage sequence? Could defensive cooldowns have prevented it? \
Skip if no deaths or no death data available.
8. **Consumable/Prep Check** — If consumable data was retrieved, list missing consumables \
and flag low-uptime buffs. Note: presence of a consumable with low uptime (<50%) \
may indicate it was only used at pull or expired mid-fight. Skip if no consumable data available.
9. **Resource Usage** — If resource data was retrieved, analyze mana/energy/rage trends. \
Healers with >10% time at zero mana are going OOM and need to adjust spell selection or \
consumables. Rogues/Ferals with frequent energy starvation may have rotation issues. \
Warriors with rage starvation may need to adjust hit rating. Skip if no resource data available.
10. **Phase Performance** — If phase breakdown data was retrieved, compare DPS and GCD uptime \
across phases. Downtime phases (transitions, air phases) are expected to show lower numbers. \
Flag significant DPS drops in non-downtime phases. Skip if no phase data available.
11. **DoT Management** — If DoT refresh data was retrieved, evaluate early refresh rates. \
<10% early refresh rate is GOOD, 10-25% is FAIR, >25% NEEDS WORK. Early refreshes waste \
GCDs and clip remaining ticks. Advise refreshing in the pandemic window (last 30% of duration). \
Skip if no DoT data available.
12. **Rotation Score** — If rotation score data was retrieved, present the letter grade and \
highlight specific rule violations. GCD uptime targets are adjusted for encounter context \
(e.g., Gruul ~85%, Netherspite ~70%). A/B grades are strong, C needs tuning, D/F \
indicates fundamental rotation issues. Skip if no rotation data available.
13. **Raid Buff Coverage** — If raid buff coverage data was retrieved (via get_buff_analysis), \
highlight buffs with low coverage (<50% of raid) or missing entirely. Key buffs like \
Battle Shout, Mark of the Wild, and Blessings should cover the full raid. \
Skip if no buff coverage data available.
14. **Actionable Checklist** — Specific, prioritized improvement suggestions as checkboxes:
   - [ ] Highest-impact improvement first
   - [ ] Second priority
   - [ ] Third priority
15. **Encouragement** — Acknowledge strengths and progress
16. **Healer Efficiency** — If analyzing a healer with overheal and resource data:
   - Overheal percentage by spell (targets: Holy Paladin ~20%, Resto Druid ~45%)
   - Mana management (time at zero mana, innervate/mana pot usage)
   - Spell selection (right spells for the situation)
   - Downranking efficiency (if applicable)
   Skip if not analyzing a healer or no overheal/resource data available.

Use the player's class/spec context to give spec-specific advice when possible.

Always provide:
- Specific, actionable advice (not generic "do more DPS")
- Context for why a number is good or bad
- Comparison points when available
- Encouragement alongside criticism

## Workflow Patterns

For thorough analysis, chain multiple tools. Common patterns:

- **Full performance review**: resolve_my_fights → get_my_performance → \
get_spec_benchmark → get_ability_breakdown → get_activity_report → \
get_cooldown_efficiency → respond with analysis

- **Raid comparison**: get_raid_execution → compare_raid_to_top → \
get_encounter_benchmarks → respond with analysis

- **Progression check**: get_progression → get_regressions → \
get_my_performance (bests_only=True) → respond with analysis

- **Gear/prep audit**: get_enchant_gem_check → get_consumable_check → \
get_gear_changes → respond with analysis

Retrieve all relevant data BEFORE writing your analysis. Call multiple \
tools if needed — don't stop after one tool call if more data would \
improve your answer.
"""
```

**Step 3: Run tests**

Run: `python3 -m pytest code/tests/agent/test_state.py code/tests/agent/test_tools.py::TestPromptContent -v`
Expected: PASS

**Step 4: Commit**

```bash
git add code/shukketsu/agent/prompts.py code/tests/agent/test_tools.py
git commit -m "refactor: merge ANALYSIS_PROMPT into SYSTEM_PROMPT, delete CRAG-only prompts"
```

---

## Task 3: Rewrite `graph.py` + update graph tests

The core change. Replace CRAG graph with ReAct loop.

**Files:**
- Rewrite: `code/shukketsu/agent/graph.py`
- Rewrite: `code/tests/agent/test_graph.py`

**Step 1: Write new graph tests**

Write `code/tests/agent/test_graph.py`:

```python
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from shukketsu.agent.graph import _normalize_tool_args, agent_node, create_graph


class TestCreateGraph:
    def test_graph_compiles(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        assert graph is not None

    def test_graph_has_agent_and_tools_nodes(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        node_names = set(graph.get_graph().nodes.keys())
        assert "agent" in node_names
        assert "tools" in node_names

    def test_graph_does_not_have_crag_nodes(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        node_names = set(graph.get_graph().nodes.keys())
        for old_node in ("route", "query", "grade", "rewrite", "analyze"):
            assert old_node not in node_names


class TestAgentNode:
    async def test_prepends_system_message(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Analysis here.")

        state = {"messages": [HumanMessage(content="How is my DPS?")]}
        await agent_node(state, llm_with_tools=mock_llm)

        call_args = mock_llm.ainvoke.call_args[0][0]
        assert isinstance(call_args[0], SystemMessage)
        assert "Shukketsu" in call_args[0].content

    async def test_returns_ai_message(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Analysis.")

        state = {"messages": [HumanMessage(content="How is my DPS?")]}
        result = await agent_node(state, llm_with_tools=mock_llm)

        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    async def test_normalizes_pascal_case_tool_args(self):
        tool_calls = [
            {"name": "get_my_performance", "args": {"EncounterName": "Gruul"}, "id": "1"}
        ]
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="", tool_calls=tool_calls
        )

        state = {"messages": [HumanMessage(content="My DPS on Gruul?")]}
        result = await agent_node(state, llm_with_tools=mock_llm)

        actual_args = result["messages"][0].tool_calls[0]["args"]
        assert "encounter_name" in actual_args
        assert "EncounterName" not in actual_args

    async def test_passes_full_message_history(self):
        from langchain_core.messages import ToolMessage

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Final analysis.")

        state = {
            "messages": [
                HumanMessage(content="My DPS?"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "get_my_performance", "args": {}, "id": "1"}],
                ),
                ToolMessage(content="DPS: 1500", tool_call_id="1"),
            ]
        }
        await agent_node(state, llm_with_tools=mock_llm)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # SystemMessage + 3 state messages
        assert len(call_args) == 4


class TestToolArgNormalization:
    def test_normalize_converts_pascal_to_snake(self):
        args = {"EncounterName": "Gruul the Dragonkiller", "PlayerName": "Lyro"}
        result = _normalize_tool_args(args)
        assert result == {"encounter_name": "Gruul the Dragonkiller", "player_name": "Lyro"}

    def test_normalize_preserves_snake_case(self):
        args = {"encounter_name": "Gruul the Dragonkiller", "player_name": "Lyro"}
        result = _normalize_tool_args(args)
        assert result == {"encounter_name": "Gruul the Dragonkiller", "player_name": "Lyro"}

    def test_normalize_handles_mixed_case(self):
        args = {"ClassName": "Warrior", "spec_name": "Arms"}
        result = _normalize_tool_args(args)
        assert result == {"class_name": "Warrior", "spec_name": "Arms"}
```

**Step 2: Run new tests — expect failures (graph.py not yet rewritten)**

Run: `python3 -m pytest code/tests/agent/test_graph.py -v`
Expected: ImportError for `agent_node` (doesn't exist yet)

**Step 3: Rewrite graph.py**

Write `code/shukketsu/agent/graph.py`:

```python
"""LangGraph ReAct agent for raid analysis."""

import logging
import re
from functools import partial
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
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
    """Invoke the LLM with tools. Normalizes PascalCase tool args from Nemotron."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)

    # Normalize PascalCase tool args from Nemotron
    if isinstance(response, AIMessage) and response.tool_calls:
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

**Step 4: Run graph tests**

Run: `python3 -m pytest code/tests/agent/test_graph.py -v`
Expected: PASS

**Step 5: Run full test suite to check for breakage**

Run: `python3 -m pytest code/tests/ -v --timeout=30`
Expected: Some failures in `test_analyze.py` (still references `"analyze"` node) and `test_state.py` already passes. Fix those in the next tasks.

**Step 6: Commit**

```bash
git add code/shukketsu/agent/graph.py code/tests/agent/test_graph.py
git commit -m "refactor: replace CRAG graph with 2-node ReAct loop (agent ⇄ tools → END)"
```

---

## Task 4: Update `analyze.py` — drop query_type + fix streaming

Update the API layer: remove `query_type` from response model, fix streaming node filter from `"analyze"` to `"agent"`, add think-tag buffer reset between agent turns.

**Files:**
- Modify: `code/shukketsu/api/routes/analyze.py`
- Modify: `code/tests/api/test_analyze.py`

**Step 1: Update test fixtures and assertions**

In `code/tests/api/test_analyze.py`, make these changes:

1. **Remove `query_type` from mock_graph fixture** (line 18):
   Change `"query_type": "my_performance"` → remove the key entirely

2. **Remove `query_type` assertion** in `test_analyze_returns_analysis` (line 60):
   Delete `assert body["query_type"] == "my_performance"`

3. **Remove `query_type` from other mock graphs**:
   - `test_analyze_strips_think_tags` (line 112): remove `"query_type": "my_performance"`
   - `test_analyze_handles_no_data` (line 134): remove `"query_type": "my_performance"`
   - `test_analyze_passes_langfuse_callbacks` (line 307): remove `"query_type": "general"`
   - `test_analyze_no_callbacks_without_handler` (line 337): remove `"query_type": "general"`

4. **Change `"analyze"` → `"agent"` in streaming tests**:
   - `test_stream_returns_sse_events` (line 160): `{"langgraph_node": "agent"}`
   - `test_stream_strips_think_tags` (lines 201, 205): `{"langgraph_node": "agent"}`
   - `test_stream_skips_non_analyze_nodes` (line 244): `{"langgraph_node": "agent"}`
   - `test_stream_passes_langfuse_callbacks` (line 372): `{"langgraph_node": "agent"}`

5. **Rename `test_stream_skips_non_analyze_nodes`** → `test_stream_skips_non_agent_nodes`:
   Change the "route" node test to verify "tools" node content is skipped.
   Change assertion: `"Routing"` → some tools-node content.

6. **Add new test for think-tag buffer reset between agent turns**:

```python
async def test_stream_resets_buffer_between_agent_turns():
    """Think-tag buffer must reset when tools node fires between agent calls."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        # First agent turn: think tags + tool call (intermediate)
        yield (
            AIMessageChunk(content="<think>Let me look that up</think>"),
            {"langgraph_node": "agent"},
        )
        # Tools node fires (resets buffer)
        yield (
            AIMessageChunk(content="DPS: 1500"),
            {"langgraph_node": "tools"},
        )
        # Second agent turn: think tags + final response
        yield (
            AIMessageChunk(content="<think>Now I can analyze</think>"),
            {"langgraph_node": "agent"},
        )
        yield (
            AIMessageChunk(content="Your DPS of 1500 is excellent."),
            {"langgraph_node": "agent"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "How is my DPS?"},
            )

    body = resp.text
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    all_tokens = "".join(evt["token"] for evt in token_events)

    assert "<think>" not in all_tokens
    assert "Let me look that up" not in all_tokens
    assert "1500 is excellent" in all_tokens
```

7. **Add new test for skipping tool_call_chunks**:

```python
async def test_stream_skips_tool_call_chunks():
    """Chunks with tool_call_chunks should not be streamed."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        # Agent produces a tool call chunk (intermediate)
        chunk = AIMessageChunk(content="")
        chunk.tool_call_chunks = [
            {"name": "get_my_performance", "args": '{"encounter_name": "Gruul"}', "id": "1"}
        ]
        yield (chunk, {"langgraph_node": "agent"})
        # Tools node
        yield (AIMessageChunk(content="DPS: 1500"), {"langgraph_node": "tools"})
        # Final agent response
        yield (
            AIMessageChunk(content="Your DPS is great."),
            {"langgraph_node": "agent"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "How is my DPS?"},
            )

    body = resp.text
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    all_tokens = "".join(evt["token"] for evt in token_events)

    assert "DPS is great" in all_tokens
    assert "get_my_performance" not in all_tokens
```

**Step 2: Run tests — expect failures (analyze.py not yet updated)**

Run: `python3 -m pytest code/tests/api/test_analyze.py -v`
Expected: Some failures (query_type still in response model, node filter still "analyze")

**Step 3: Update analyze.py**

In `code/shukketsu/api/routes/analyze.py`:

1. **Remove `query_type` from `AnalyzeResponse`** (line 53):
```python
class AnalyzeResponse(BaseModel):
    answer: str
```

2. **Simplify non-streaming endpoint** (line 91-93):
```python
    return AnalyzeResponse(answer=answer)
```

3. **Rewrite streaming event_generator** — new filter logic:

```python
    async def event_generator():
        buffer = ""
        think_done = False

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
                    node = (
                        metadata.get("langgraph_node")
                        if isinstance(metadata, dict) else None
                    )

                    # Reset think-tag buffer between agent turns
                    if node == "tools":
                        buffer = ""
                        think_done = False
                        continue

                    if node != "agent":
                        continue

                    if not hasattr(chunk, "content") or not chunk.content:
                        continue

                    # Skip tool call chunks (intermediate turns)
                    if getattr(chunk, "tool_call_chunks", None):
                        continue

                    token = chunk.content

                    if not think_done:
                        buffer += token
                        if len(buffer) > _MAX_THINK_BUFFER:
                            cleaned = _strip_think_tags(buffer)
                            if cleaned.strip():
                                yield {
                                    "data": json.dumps(
                                        {"token": cleaned}
                                    )
                                }
                            buffer = ""
                            think_done = True
                            continue
                        if "</think>" in buffer:
                            after = THINK_PATTERN.sub("", buffer)
                            think_done = True
                            buffer = ""
                            if after.strip():
                                yield {"data": json.dumps({"token": after})}
                        continue

                    yield {"data": json.dumps({"token": token})}

                # If we buffered but never saw </think>, flush as content
                if buffer and not think_done:
                    cleaned = _strip_think_tags(buffer)
                    if cleaned.strip():
                        yield {"data": json.dumps({"token": cleaned})}

                yield {"data": json.dumps({"done": True})}

        except asyncio.CancelledError:
            logger.info(
                "Streaming analysis cancelled (client disconnect)"
            )
            return
        except Exception:
            logger.exception("Streaming analysis failed")
            yield {"event": "error", "data": json.dumps({"detail": "Analysis failed"})}
```

**Step 4: Run analyze tests**

Run: `python3 -m pytest code/tests/api/test_analyze.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/api/routes/analyze.py code/tests/api/test_analyze.py
git commit -m "refactor: drop query_type from API, update streaming for ReAct agent node"
```

---

## Task 5: Update frontend — remove query_type

Remove `query_type` from the TypeScript types, API client, and UI components.

**Files:**
- Modify: `code/frontend/src/lib/types.ts`
- Modify: `code/frontend/src/lib/api.ts`
- Modify: `code/frontend/src/pages/ChatPage.tsx`
- Modify: `code/frontend/src/components/chat/MessageBubble.tsx`

**Step 1: Remove `queryType` from ChatMessage type**

In `code/frontend/src/lib/types.ts`:
- Remove `queryType?: string | null` from `ChatMessage`
- Remove `query_type: string | null` from `AnalyzeResponse`

**Step 2: Update API client**

In `code/frontend/src/lib/api.ts`:
- Change `onDone: (queryType: string | null) => void` → `onDone: () => void`
- Change `onDone(event.query_type ?? null)` → `onDone()`

**Step 3: Update ChatPage.tsx**

In `code/frontend/src/pages/ChatPage.tsx`:
- Change the `onDone` callback (lines 49-54):

```typescript
        () => {
          setStreaming(false)
        },
```

**Step 4: Update MessageBubble.tsx**

In `code/frontend/src/components/chat/MessageBubble.tsx`:
- Remove the `queryType` badge (lines 24-28):

Delete:
```tsx
        {message.queryType && (
          <span className="mt-2 inline-block rounded bg-zinc-700/50 px-2 py-0.5 text-xs text-zinc-400">
            {message.queryType}
          </span>
        )}
```

**Step 5: Verify frontend builds**

Run: `cd /home/lyro/nvidia-workbench/wcl-tbc-analyzer/code/frontend && npx tsc --noEmit`
Expected: No TypeScript errors

**Step 6: Commit**

```bash
git add code/frontend/
git commit -m "refactor: remove query_type from frontend types, API client, and UI"
```

---

## Task 6: Lint + full test suite

**Step 1: Lint**

Run: `python3 -m ruff check code/`
Expected: Clean (fix any unused import warnings from deleted prompts)

**Step 2: Full test suite**

Run: `python3 -m pytest code/tests/ -v --timeout=30`
Expected: All tests pass. Test count should drop by ~15 (removed CRAG-specific tests).

**Step 3: Fix any remaining failures**

If any tests fail, investigate and fix. Common issues:
- Stale imports of `GRADER_PROMPT`, `ROUTER_PROMPT`, `REWRITE_PROMPT`, `ANALYSIS_PROMPT`
- Stale imports of `MAX_RETRIES`, `route_query`, `grade_results`, `_format_messages`
- Any test still referencing `query_type` in graph/analyze results

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve remaining test/lint issues from ReAct migration"
```

---

## Task 7: Update CLAUDE.md

Update project documentation to reflect the new architecture.

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md**

Key changes:
- **CRAG agent flow** section → replace with ReAct diagram:
  ```
  agent ⇄ tools → END
  (LLM decides when to call tools and when to respond)
  ```
- Remove references to: route, grade, rewrite, MAX_RETRIES, query_type, GRADER_PROMPT, ROUTER_PROMPT, REWRITE_PROMPT
- Update graph.py description: "6 nodes" → "2 nodes (agent + tools)"
- Update `AnalyzerState` description: remove query_type, grade, retry_count fields
- Update streaming description: node filter from `"analyze"` to `"agent"`
- Update API response model: remove `query_type` field
- Add to **Resolved issues**: "CRAG → ReAct simplification: collapsed 6-node CRAG graph..."

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for ReAct agent architecture"
```

---

## Summary

| Task | What | Files | Lines changed |
|------|------|-------|---------------|
| 1 | Simplify state.py | 2 | -25 |
| 2 | Merge prompts | 2 | -35 (3 prompts deleted) |
| 3 | Rewrite graph.py + tests | 2 | -150 (graph), -100 (tests) |
| 4 | Update analyze.py + tests | 2 | -10 (analyze), +40 (new tests) |
| 5 | Update frontend | 4 | -15 |
| 6 | Lint + full test suite | — | Fix-ups only |
| 7 | Update CLAUDE.md | 1 | Docs only |

**Total: ~7 commits, ~250 fewer production lines, ~100 fewer test lines**
