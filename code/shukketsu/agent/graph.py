"""LangGraph ReAct agent for raid analysis.

Architecture: prefetch → agent ⇄ tools → END

The prefetch node classifies intent from the user's first message and
auto-fetches relevant data BEFORE the LLM runs. This makes the initial
analysis deterministic and reliable — the LLM receives data and analyzes
it instead of choosing which tool to call (which Nemotron does poorly).

Intent routing covers 7 intents: report_analysis, player_analysis,
compare_to_top, benchmarks, progression, specific_tool, leaderboard.
"""

import contextlib
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

from shukketsu.agent.intent import (
    IntentResult,
    _extract_encounter_name,
    _extract_player_names,
    classify_intent,
)
from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState

logger = logging.getLogger(__name__)

# Maximum fight details to prefetch (prevents slow prefetch for large raids)
_MAX_PREFETCH_FIGHTS = 5

# WCL report codes: 16+ alphanumeric chars (typically 16 or 32 hex).
# Also matches codes inside URLs like /reports/CODE
_REPORT_CODE_RE = re.compile(r'(?:reports/)?([a-zA-Z0-9]{16,40})')

# _extract_player_names imported from intent.py (single source of truth)

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


# Argument name alias map: hallucinated arg name → correct arg name
_ARG_ALIASES: dict[str, str] = {
    "term": "encounter_name",
    "playername": "player_name",
    "player": "player_name",
    "reportcode": "report_code",
    "report_id": "report_code",
    "is_id": "report_code",
    "code": "report_code",
    "fight_id_str": "fight_id",
    "fightid": "fight_id",
    "encounter": "encounter_name",
    "boss": "encounter_name",
    "boss_name": "encounter_name",
    "classname": "class_name",
    "specname": "spec_name",
    "charactername": "character_name",
}

# Fields that should be coerced to int when passed as string
_INT_FIELDS = frozenset({"fight_id", "count"})

# Fields that should be coerced to bool when passed as string
_BOOL_FIELDS = frozenset({"bests_only"})


def _normalize_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    """Normalize tool argument keys and coerce value types.

    1. PascalCase → snake_case (e.g. EncounterName → encounter_name)
    2. Alias map (e.g. term → encounter_name, reportcode → report_code)
    3. Type coercion (fight_id: "8" → 8, bests_only: "true" → True)
    """
    normalized = {}
    for key, value in args.items():
        # PascalCase → snake_case
        snake_key = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", key).lower()
        # Apply alias
        final_key = _ARG_ALIASES.get(snake_key, snake_key)
        # Type coercion for int fields
        if final_key in _INT_FIELDS and isinstance(value, str):
            with contextlib.suppress(ValueError):
                value = int(value)
        # Type coercion for bool fields
        if final_key in _BOOL_FIELDS and isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")
        normalized[final_key] = value
    return normalized


# Semantic alias map: hallucinated name → correct tool name
_TOOL_ALIASES: dict[str, str] = {
    "analyze_report": "get_raid_execution",
    "analyze_fight": "get_raid_execution",
    "get_analysis": "get_raid_execution",
    "get_analysis_metrics": "get_activity_report",
    "get_analysis_report": "get_activity_report",
    "get_player_progression_over_time": "get_progression",
    "get_character_profile": "get_progression",
    "search": "search_fights",
    "find_fights": "search_fights",
    "get_report": "get_raid_execution",
    "get_report_analysis": "get_raid_execution",
    "get_player_performance": "get_my_performance",
    "get_benchmarks": "get_encounter_benchmarks",
    "get_leaderboard": "get_spec_leaderboard",
    "get_rankings": "get_top_rankings",
    "get_deaths": "get_death_analysis",
    "get_rotation": "get_rotation_score",
    "get_cooldowns": "get_cooldown_efficiency",
    "get_consumables": "get_consumable_check",
    "get_buffs": "get_buff_analysis",
    "get_abilities": "get_ability_breakdown",
    "get_gear": "get_gear_changes",
    "get_enchants": "get_enchant_gem_check",
    "get_resources": "get_resource_usage",
    "get_dots": "get_dot_management",
    "get_phases": "get_phase_analysis",
    "get_cancels": "get_cancelled_casts",
}


def _fix_tool_name(name: str, valid_names: set[str]) -> str:
    """Fix hallucinated tool names via alias map + fuzzy matching.

    Priority: exact match → alias map → camelCase conversion → alias of
    snake version → fuzzy match (high cutoff) → return original.
    """
    if name in valid_names:
        return name

    # Check alias map
    alias = _TOOL_ALIASES.get(name)
    if alias and alias in valid_names:
        logger.info("Fixed aliased tool name: %s → %s", name, alias)
        return alias

    # Try snake_case conversion (e.g. getMyPerformance → get_my_performance)
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()
    if snake in valid_names:
        logger.info("Fixed camelCase tool name: %s → %s", name, snake)
        return snake

    # Check alias for snake_case version too
    alias = _TOOL_ALIASES.get(snake)
    if alias and alias in valid_names:
        logger.info(
            "Fixed aliased tool name (via snake): %s → %s", name, alias
        )
        return alias

    # Fuzzy match with higher cutoff (last resort)
    matches = get_close_matches(name, list(valid_names), n=1, cutoff=0.7)
    if matches:
        logger.warning("Fuzzy-matched tool name: %s → %s", name, matches[0])
        return matches[0]

    logger.warning("Unknown tool name '%s', no match found", name)
    return name


def _auto_repair_args(
    tool_name: str,
    args: dict[str, Any],
    messages: list,
) -> dict[str, Any]:
    """Fill missing required args from conversation context.

    Scans prior messages (human text, tool call args, tool results) to find
    report_code, player_name, and encounter_name that the LLM forgot to include.
    Never overwrites args that are already present.
    """
    repaired = dict(args)

    # First, try to extract from prior tool_call args (most reliable source)
    if "report_code" not in repaired or "player_name" not in repaired:
        for m in reversed(messages):
            if (isinstance(m, AIMessage) and hasattr(m, "tool_calls")
                    and m.tool_calls):
                for tc in m.tool_calls:
                    tc_args = tc.get("args", {})
                    if ("report_code" not in repaired
                            and "report_code" in tc_args):
                        repaired["report_code"] = tc_args["report_code"]
                    if ("player_name" not in repaired
                            and "player_name" in tc_args):
                        repaired["player_name"] = tc_args["player_name"]

    # Fall back to scanning all message text content
    all_text = " ".join(
        m.content for m in messages
        if hasattr(m, "content") and isinstance(m.content, str)
    )

    if "report_code" not in repaired:
        code = _extract_report_code(all_text)
        if code:
            repaired["report_code"] = code

    if "player_name" not in repaired:
        names = _extract_player_names(all_text)
        if names:
            repaired["player_name"] = names[0]

    if "encounter_name" not in repaired:
        enc = _extract_encounter_name(all_text)
        if enc:
            repaired["encounter_name"] = enc

    return repaired


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


# Maximum tool errors before graceful fallback
_MAX_TOOL_ERRORS = 3

_RETRY_HINT = (
    "The previous tool call failed. Read the error message carefully, "
    "fix the parameters, and retry with corrected arguments. "
    "Do NOT apologize or ask the user for help."
)

_FALLBACK_MESSAGE = (
    "I wasn't able to retrieve the data needed for this analysis. "
    "This may be due to missing data in the database. "
    "Try rephrasing your question or specifying different parameters."
)


def _detect_tool_error(messages: list) -> bool:
    """Check if the last message is a ToolMessage containing an error."""
    if not messages:
        return False
    last = messages[-1]
    return (
        isinstance(last, ToolMessage)
        and isinstance(last.content, str)
        and last.content.startswith("Error")
    )


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

    Includes retry budget: tracks tool errors and injects retry hints.
    After MAX_TOOL_ERRORS, returns a graceful fallback instead of retrying.
    """
    messages = state["messages"]
    intent = state.get("intent")
    error_count = state.get("tool_error_count", 0)

    # Detect tool errors and track count
    has_error = _detect_tool_error(messages)
    if has_error:
        error_count += 1

    # Graceful fallback after too many errors
    if error_count >= _MAX_TOOL_ERRORS:
        return {
            "messages": [AIMessage(content=_FALLBACK_MESSAGE)],
            "tool_error_count": error_count,
        }

    # Filter tools based on intent (reduces hallucination)
    filtered_tools = _get_tools_for_intent(intent, all_tools)
    llm_with_tools = llm.bind_tools(filtered_tools) if filtered_tools else llm
    filtered_names = (
        {t.name for t in filtered_tools} if filtered_tools else tool_names
    )

    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    # Inject retry hint after tool errors
    if has_error:
        full_messages.append(SystemMessage(content=_RETRY_HINT))

    response = await llm_with_tools.ainvoke(full_messages)

    # Fix hallucinated tool names, normalize args, and auto-repair missing args
    if isinstance(response, AIMessage) and response.tool_calls:
        for tc in response.tool_calls:
            tc["name"] = _fix_tool_name(tc["name"], filtered_names)
            tc["args"] = _normalize_tool_args(tc["args"])
            tc["args"] = _auto_repair_args(
                tc["name"], tc["args"], messages,
            )

    result: dict[str, Any] = {"messages": [response]}

    # Update error count: increment on error, reset on successful response
    if has_error:
        result["tool_error_count"] = error_count
    elif not has_error and error_count > 0:
        result["tool_error_count"] = 0

    return result


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
