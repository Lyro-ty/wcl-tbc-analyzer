"""LangGraph ReAct agent for raid analysis.

Architecture: prefetch → agent ⇄ tools → END

The prefetch node classifies intent from the user's first message and
auto-fetches relevant data BEFORE the LLM runs. This makes the initial
analysis deterministic and reliable — the LLM receives data and analyzes
it instead of choosing which tool to call (which Nemotron does poorly).

Intent routing covers 7 intents: report_analysis, player_analysis,
compare_to_top, benchmarks, progression, specific_tool, leaderboard.
"""

import logging
import re
from difflib import get_close_matches
from functools import partial
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy import text

from shukketsu.agent.intent import IntentResult, classify_intent
from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState

logger = logging.getLogger(__name__)

# Maximum fight details to prefetch (prevents slow prefetch for large raids)
_MAX_PREFETCH_FIGHTS = 5

# WCL report codes: 16+ alphanumeric chars (typically 16 or 32 hex).
# Also matches codes inside URLs like /reports/CODE
_REPORT_CODE_RE = re.compile(r'(?:reports/)?([a-zA-Z0-9]{16,40})')

# Player name detection: capitalized words 3-15 chars, excluding common
# English words and boss names that would produce false positives.
_PLAYER_NAME_RE = re.compile(r'\b([A-Z][a-z]{2,15})\b')
_COMMON_WORDS = frozenset({
    "The", "Can", "Please", "What", "How", "Did", "Does", "Show",
    "Tell", "Analyze", "Report", "Check", "Compare", "Pull", "Get",
    "Could", "Would", "Should", "Have", "Been", "Will", "Also",
    "High", "King", "Gruul", "Magtheridon", "Prince", "Maiden",
    "Moroes", "Nightbane", "Netherspite", "Curator", "Aran",
    "Attumen", "Opera", "Illhoof", "Shade", "Malchezaar",
    "Karazhan", "Raid", "Execution", "Summary", "Kills", "Wipes",
    "Better", "Where", "When", "Which", "Help", "With", "From",
    "About", "Their", "They", "That", "This", "These", "Those",
})

# Tools that require fight_id as an argument
_TOOLS_NEEDING_FIGHT_ID = frozenset({
    "get_fight_details", "get_deaths_and_mechanics",
    "get_death_analysis", "get_activity_report", "get_cooldown_efficiency",
    "get_cancelled_casts", "get_consumable_check", "get_resource_usage",
    "get_dot_management", "get_rotation_score", "get_phase_analysis",
    "get_enchant_gem_check", "get_ability_breakdown", "get_buff_analysis",
    "get_overheal_analysis",
})

# Tool name → module path for lazy lookup
_TOOL_MODULE_MAP: dict[str, str] = {
    # Player tools
    "get_my_performance": "player_tools",
    "get_top_rankings": "player_tools",
    "compare_to_top": "player_tools",
    "get_fight_details": "player_tools",
    "get_progression": "player_tools",
    "get_deaths_and_mechanics": "player_tools",
    "search_fights": "player_tools",
    "get_spec_leaderboard": "player_tools",
    "resolve_my_fights": "player_tools",
    "get_wipe_progression": "player_tools",
    "get_regressions": "player_tools",
    # Raid tools
    "compare_raid_to_top": "raid_tools",
    "compare_two_raids": "raid_tools",
    "get_raid_execution": "raid_tools",
    # Table tools
    "get_ability_breakdown": "table_tools",
    "get_buff_analysis": "table_tools",
    "get_overheal_analysis": "table_tools",
    # Event tools
    "get_death_analysis": "event_tools",
    "get_activity_report": "event_tools",
    "get_cooldown_efficiency": "event_tools",
    "get_cancelled_casts": "event_tools",
    "get_consumable_check": "event_tools",
    "get_resource_usage": "event_tools",
    "get_dot_management": "event_tools",
    "get_rotation_score": "event_tools",
    "get_gear_changes": "event_tools",
    "get_phase_analysis": "event_tools",
    "get_enchant_gem_check": "event_tools",
    # Benchmark tools
    "get_encounter_benchmarks": "benchmark_tools",
    "get_spec_benchmark": "benchmark_tools",
}


# Intent → allowed tool names (reduces hallucination by limiting choices)
_INTENT_TOOLS: dict[str, set[str]] = {
    "report_analysis": {
        "get_deaths_and_mechanics", "get_encounter_benchmarks",
        "search_fights", "get_fight_details", "get_raid_execution",
        "compare_raid_to_top", "get_wipe_progression",
        "get_spec_leaderboard",
    },
    "player_analysis": {
        "get_activity_report", "compare_to_top", "get_rotation_score",
        "get_cooldown_efficiency", "get_ability_breakdown",
        "get_buff_analysis", "get_consumable_check",
        "get_enchant_gem_check", "search_fights",
        "get_death_analysis", "get_resource_usage",
    },
    "compare_to_top": {
        "compare_raid_to_top", "get_encounter_benchmarks",
        "get_spec_benchmark", "compare_two_raids",
        "get_spec_leaderboard",
    },
    "benchmarks": {
        "get_encounter_benchmarks", "get_spec_benchmark",
        "get_spec_leaderboard",
    },
    "progression": {
        "get_progression", "get_regressions", "resolve_my_fights",
        "get_my_performance",
    },
    "leaderboard": {
        "get_spec_leaderboard", "get_encounter_benchmarks",
        "get_top_rankings",
    },
    # "specific_tool" and None → all tools (LLM needs full access)
}


def _get_tools_for_intent(intent: str | None, all_tools: list) -> list:
    """Filter tools based on detected intent.

    Returns a subset of tools relevant to the intent, reducing the chance
    of hallucinated tool calls. Unknown intent or specific_tool intent
    returns all tools.
    """
    allowed = _INTENT_TOOLS.get(intent)
    if allowed is None:
        return all_tools
    return [t for t in all_tools if t.name in allowed]


def _lookup_tool(name: str) -> Any | None:
    """Lazy-import a tool function by name to avoid circular imports."""
    module_name = _TOOL_MODULE_MAP.get(name)
    if not module_name:
        return None
    import importlib
    mod = importlib.import_module(f"shukketsu.agent.tools.{module_name}")
    return getattr(mod, name, None)


def _extract_report_code(text: str) -> str | None:
    """Extract a WCL report code from user text."""
    match = _REPORT_CODE_RE.search(text)
    return match.group(1) if match else None


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


def _fix_tool_name(name: str, valid_names: set[str]) -> str:
    """Fix hallucinated tool names via fuzzy matching.

    Nemotron sometimes invents tool names (e.g. 'get_analysis' instead of
    'get_raid_execution'). This attempts to recover by matching to the
    closest valid tool name.
    """
    if name in valid_names:
        return name
    # Try snake_case conversion (e.g. getMyPerformance → get_my_performance)
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()
    if snake in valid_names:
        logger.info("Fixed camelCase tool name: %s → %s", name, snake)
        return snake
    # Fuzzy match
    matches = get_close_matches(name, list(valid_names), n=1, cutoff=0.5)
    if matches:
        logger.warning(
            "Fixed hallucinated tool name: %s → %s", name, matches[0]
        )
        return matches[0]
    logger.warning("Unknown tool name '%s', no close match found", name)
    return name


def _extract_player_names(text: str) -> list[str]:
    """Extract candidate player names from user text."""
    return [
        m.group(1) for m in _PLAYER_NAME_RE.finditer(text)
        if m.group(1) not in _COMMON_WORDS
    ]


def _inject_tool_result(
    tool_name: str, args: dict[str, Any], result: str,
) -> list:
    """Create synthetic AIMessage + ToolMessage pair for prefetched data."""
    call_id = f"prefetch_{tool_name}_{hash(str(args)) % 100000}"
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "args": args, "id": call_id}],
    )
    tool_msg = ToolMessage(content=result, tool_call_id=call_id)
    return [ai_msg, tool_msg]


async def _get_kill_fight_ids(report_code: str) -> list[int]:
    """Get WCL fight IDs for kill fights in a report (lightweight DB query).

    Returns fight_id (WCL's per-report fight number), NOT the DB primary key,
    since get_fight_details queries by f.fight_id.
    """
    from shukketsu.agent.tool_utils import _get_session

    session = await _get_session()
    try:
        result = await session.execute(
            text(
                "SELECT fight_id FROM fights "
                "WHERE report_code = :code AND kill = true "
                "ORDER BY fight_id"
            ),
            {"code": report_code},
        )
        return [row[0] for row in result.fetchall()]
    finally:
        await session.close()


# --------------------------------------------------------------------------- #
# Intent-based prefetch dispatch
# --------------------------------------------------------------------------- #


async def _prefetch_report(intent: IntentResult) -> list:
    """Prefetch raid execution + fight details for report analysis."""
    if not intent.report_code:
        return []

    from shukketsu.agent.tools.player_tools import get_fight_details
    from shukketsu.agent.tools.raid_tools import get_raid_execution

    code = intent.report_code
    result = await get_raid_execution.ainvoke({"report_code": code})
    injected = _inject_tool_result(
        "get_raid_execution", {"report_code": code}, result,
    )

    fight_ids = await _get_kill_fight_ids(code)
    for fight_id in fight_ids[:_MAX_PREFETCH_FIGHTS]:
        detail = await get_fight_details.ainvoke({
            "report_code": code, "fight_id": fight_id,
        })
        injected.extend(_inject_tool_result(
            "get_fight_details",
            {"report_code": code, "fight_id": fight_id},
            detail,
        ))

    return injected


async def _prefetch_player(intent: IntentResult) -> list:
    """Prefetch raid + fight details + activity reports for player analysis."""
    if not intent.report_code:
        return []

    from shukketsu.agent.tools.event_tools import get_activity_report
    from shukketsu.agent.tools.player_tools import get_fight_details
    from shukketsu.agent.tools.raid_tools import get_raid_execution

    code = intent.report_code
    result = await get_raid_execution.ainvoke({"report_code": code})
    injected = _inject_tool_result(
        "get_raid_execution", {"report_code": code}, result,
    )

    fight_ids = await _get_kill_fight_ids(code)
    for fight_id in fight_ids[:_MAX_PREFETCH_FIGHTS]:
        detail = await get_fight_details.ainvoke({
            "report_code": code, "fight_id": fight_id,
        })
        injected.extend(_inject_tool_result(
            "get_fight_details",
            {"report_code": code, "fight_id": fight_id},
            detail,
        ))

        # Fetch activity report for each named player on each fight
        for player in intent.player_names:
            activity = await get_activity_report.ainvoke({
                "report_code": code,
                "fight_id": fight_id,
                "player_name": player,
            })
            injected.extend(_inject_tool_result(
                "get_activity_report",
                {
                    "report_code": code,
                    "fight_id": fight_id,
                    "player_name": player,
                },
                activity,
            ))

    return injected


async def _prefetch_compare(intent: IntentResult) -> list:
    """Prefetch comparison data."""
    if intent.report_code:
        from shukketsu.agent.tools.raid_tools import compare_raid_to_top

        result = await compare_raid_to_top.ainvoke({
            "report_code": intent.report_code,
        })
        return _inject_tool_result(
            "compare_raid_to_top",
            {"report_code": intent.report_code},
            result,
        )

    if intent.encounter_name:
        from shukketsu.agent.tools.benchmark_tools import (
            get_encounter_benchmarks,
        )

        result = await get_encounter_benchmarks.ainvoke({
            "encounter_name": intent.encounter_name,
        })
        return _inject_tool_result(
            "get_encounter_benchmarks",
            {"encounter_name": intent.encounter_name},
            result,
        )

    return []


async def _prefetch_benchmarks(intent: IntentResult) -> list:
    """Prefetch benchmark data."""
    injected: list = []

    if intent.encounter_name:
        from shukketsu.agent.tools.benchmark_tools import (
            get_encounter_benchmarks,
        )

        result = await get_encounter_benchmarks.ainvoke({
            "encounter_name": intent.encounter_name,
        })
        injected.extend(_inject_tool_result(
            "get_encounter_benchmarks",
            {"encounter_name": intent.encounter_name},
            result,
        ))

    if intent.class_name and intent.spec_name and intent.encounter_name:
        from shukketsu.agent.tools.benchmark_tools import get_spec_benchmark

        args = {
            "encounter_name": intent.encounter_name,
            "class_name": intent.class_name,
            "spec_name": intent.spec_name,
        }
        result = await get_spec_benchmark.ainvoke(args)
        injected.extend(_inject_tool_result(
            "get_spec_benchmark", args, result,
        ))

    return injected


async def _prefetch_progression(intent: IntentResult) -> list:
    """Prefetch progression data for a player."""
    if not intent.player_names:
        return []

    from shukketsu.agent.tools.player_tools import get_progression

    args: dict[str, Any] = {"character_name": intent.player_names[0]}
    if intent.encounter_name:
        args["encounter_name"] = intent.encounter_name

    result = await get_progression.ainvoke(args)
    return _inject_tool_result("get_progression", args, result)


async def _prefetch_leaderboard(intent: IntentResult) -> list:
    """Prefetch spec leaderboard for an encounter."""
    if not intent.encounter_name:
        return []

    from shukketsu.agent.tools.player_tools import get_spec_leaderboard

    result = await get_spec_leaderboard.ainvoke({
        "encounter_name": intent.encounter_name,
    })
    return _inject_tool_result(
        "get_spec_leaderboard",
        {"encounter_name": intent.encounter_name},
        result,
    )


async def _prefetch_specific(intent: IntentResult) -> list:
    """Prefetch a specific tool's results with available context.

    Resolves fight_id from DB when the tool needs it and we have a report code.
    Builds args from intent context (report_code, player_name, encounter_name).
    """
    if not intent.specific_tool:
        return []

    tool_fn = _lookup_tool(intent.specific_tool)
    if tool_fn is None:
        return []

    args: dict[str, Any] = {}
    if intent.report_code:
        args["report_code"] = intent.report_code
    if intent.player_names:
        args["player_name"] = intent.player_names[0]
    if intent.encounter_name:
        args["encounter_name"] = intent.encounter_name

    # Resolve fight_id if needed
    if (intent.specific_tool in _TOOLS_NEEDING_FIGHT_ID
            and intent.report_code and "fight_id" not in args):
        fight_ids = await _get_kill_fight_ids(intent.report_code)
        if fight_ids:
            args["fight_id"] = fight_ids[0]

    try:
        result = await tool_fn.ainvoke(args)
        return _inject_tool_result(intent.specific_tool, args, result)
    except Exception as e:
        logger.warning(
            "Prefetch %s failed: %s — deferring to LLM",
            intent.specific_tool, e,
        )
        return []


_PREFETCH_DISPATCH = {
    "report_analysis": _prefetch_report,
    "player_analysis": _prefetch_player,
    "compare_to_top": _prefetch_compare,
    "benchmarks": _prefetch_benchmarks,
    "progression": _prefetch_progression,
    "specific_tool": _prefetch_specific,
    "leaderboard": _prefetch_leaderboard,
}


async def prefetch_node(state: dict[str, Any]) -> dict[str, Any]:
    """Intent-based prefetch: classify what the user wants and fetch it.

    Runs before the LLM agent. Classifies the user's first message into
    one of 7 intents and fetches the relevant data deterministically.
    The LLM then sees the data and can analyze it immediately.
    """
    messages = state["messages"]

    # Only on first turn (no prior tool results)
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    if any(isinstance(m, ToolMessage) for m in messages):
        return {}

    user_text = messages[-1].content
    intent = classify_intent(user_text)

    if intent.intent is None:
        return {}

    handler = _PREFETCH_DISPATCH.get(intent.intent)
    if handler is None:
        return {}

    logger.info(
        "Prefetch: intent=%s, report=%s, players=%s, tool=%s",
        intent.intent, intent.report_code,
        intent.player_names, intent.specific_tool,
    )

    injected = await handler(intent)

    result: dict[str, Any] = {"intent": intent.intent}
    if injected:
        result["messages"] = injected
    return result


# --------------------------------------------------------------------------- #
# Agent node
# --------------------------------------------------------------------------- #


async def agent_node(
    state: dict[str, Any],
    *,
    llm: Any,
    all_tools: list,
    tool_names: set[str],
) -> dict[str, Any]:
    """Invoke the LLM with tools and the system prompt.

    Dynamically binds a filtered tool set based on the detected intent.
    After the prefetch node has injected data, the LLM receives it and
    can analyze directly. For follow-up questions, tools remain available.
    """
    messages = state["messages"]
    intent = state.get("intent")

    # Filter tools based on intent (reduces hallucination)
    filtered_tools = _get_tools_for_intent(intent, all_tools)
    llm_with_tools = llm.bind_tools(filtered_tools) if filtered_tools else llm
    filtered_names = {t.name for t in filtered_tools} if filtered_tools else tool_names

    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = await llm_with_tools.ainvoke(full_messages)

    # Fix hallucinated tool names and normalize PascalCase args
    if isinstance(response, AIMessage) and response.tool_calls:
        for tc in response.tool_calls:
            tc["name"] = _fix_tool_name(tc["name"], filtered_names)
            tc["args"] = _normalize_tool_args(tc["args"])

    return {"messages": [response]}


# --------------------------------------------------------------------------- #
# Graph construction
# --------------------------------------------------------------------------- #


def create_graph(llm: Any, tools: list) -> CompiledStateGraph:
    """Create and compile the ReAct agent graph.

    Graph: prefetch → agent ⇄ tools → END

    Tools are bound dynamically per turn based on detected intent,
    reducing the number of tools the LLM sees for focused queries.
    """
    tool_names = {t.name for t in tools} if tools else set()

    graph = StateGraph(AnalyzerState)

    graph.add_node("prefetch", prefetch_node)
    graph.add_node("agent", partial(
        agent_node,
        llm=llm,
        all_tools=tools,
        tool_names=tool_names,
    ))
    graph.add_node("tools", ToolNode(tools) if tools else _noop_tool_node)

    graph.set_entry_point("prefetch")
    graph.add_edge("prefetch", "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


async def _noop_tool_node(state: dict[str, Any]) -> dict[str, Any]:
    """Placeholder when no tools are configured."""
    return {}
