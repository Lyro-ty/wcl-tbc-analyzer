"""LangGraph ReAct agent for raid analysis.

Architecture: prefetch → agent ⇄ tools → END

The prefetch node detects report codes in the user's first message and
auto-fetches raid data BEFORE the LLM runs. This makes the initial analysis
deterministic and reliable — the LLM receives data and analyzes it instead
of choosing which tool to call (which Nemotron does poorly).
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

from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState

logger = logging.getLogger(__name__)

# WCL report codes: 16+ alphanumeric chars (typically 16 or 32 hex).
# Also matches codes inside URLs like /reports/CODE
_REPORT_CODE_RE = re.compile(r'(?:reports/)?([a-zA-Z0-9]{16,40})')

# Keywords indicating user wants a specific tool, not general raid analysis.
# When present, skip prefetch and let the LLM choose the right tool.
_SPECIFIC_TOOL_KEYWORDS = re.compile(
    r'\b(rotation|deaths?|cooldown|consumable|buff|ability|gear|enchant|gem|'
    r'resource|mana|cast|cancel|dot|phase|overheal|wipe)\b',
    re.IGNORECASE,
)

# Player name detection: capitalized words 3-15 chars, excluding common English
# words and boss names that would produce false positives.
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
        logger.warning("Fixed hallucinated tool name: %s → %s", name, matches[0])
        return matches[0]
    logger.warning("Unknown tool name '%s', no close match found", name)
    return name


def _extract_player_names(text: str) -> list[str]:
    """Extract candidate player names from user text."""
    return [
        m.group(1) for m in _PLAYER_NAME_RE.finditer(text)
        if m.group(1) not in _COMMON_WORDS
    ]


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


async def prefetch_node(state: dict[str, Any]) -> dict[str, Any]:
    """Auto-fetch report data when a report code is detected.

    Runs before the LLM agent. If the user's first message contains a report
    code, this node calls get_raid_execution directly and injects the results
    into the message history. The LLM then sees the data and can analyze it
    immediately without needing to select tools.

    When a player name is also detected, additionally fetches per-fight details
    for all kill fights so the LLM has player-level data to analyze.
    """
    messages = state["messages"]

    # Only on first turn (single user message, no prior tool results)
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    if any(isinstance(m, ToolMessage) for m in messages):
        return {}

    # Skip when user asks for a specific tool (rotation, deaths, etc.)
    user_text = messages[-1].content
    if _SPECIFIC_TOOL_KEYWORDS.search(user_text):
        return {}

    report_code = _extract_report_code(user_text)
    if not report_code:
        return {}

    # Import here to avoid circular dependency (tools → tool_utils → graph)
    from shukketsu.agent.tools.raid_tools import get_raid_execution

    logger.info("Prefetching raid data for report %s", report_code)
    result = await get_raid_execution.ainvoke({"report_code": report_code})

    # Inject as a synthetic tool call + result so the LLM sees the data
    tool_call_id = f"prefetch_{report_code}"
    ai_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_raid_execution",
            "args": {"report_code": report_code},
            "id": tool_call_id,
        }],
    )
    tool_msg = ToolMessage(content=result, tool_call_id=tool_call_id)
    injected: list = [ai_msg, tool_msg]

    # If player names detected, also fetch per-fight details for kills
    player_names = _extract_player_names(user_text)
    if player_names:
        fight_ids = await _get_kill_fight_ids(report_code)
        if fight_ids:
            from shukketsu.agent.tools.player_tools import get_fight_details

            logger.info(
                "Prefetching fight details for %d kills (players: %s)",
                len(fight_ids), ", ".join(player_names),
            )
            for fight_id in fight_ids:
                detail_result = await get_fight_details.ainvoke({
                    "report_code": report_code,
                    "fight_id": fight_id,
                })
                detail_id = f"prefetch_fight_{fight_id}"
                detail_ai = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "get_fight_details",
                        "args": {
                            "report_code": report_code,
                            "fight_id": fight_id,
                        },
                        "id": detail_id,
                    }],
                )
                detail_tool = ToolMessage(
                    content=detail_result, tool_call_id=detail_id,
                )
                injected.extend([detail_ai, detail_tool])

    return {"messages": injected}


async def agent_node(
    state: dict[str, Any],
    *,
    llm_with_tools: Any,
    tool_names: set[str],
) -> dict[str, Any]:
    """Invoke the LLM with tools and the system prompt.

    After the prefetch node has injected raid data, the LLM receives data
    to analyze directly. For follow-up questions, tools remain available.
    """
    messages = state["messages"]
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = await llm_with_tools.ainvoke(full_messages)

    # Fix hallucinated tool names and normalize PascalCase args
    if isinstance(response, AIMessage) and response.tool_calls:
        for tc in response.tool_calls:
            tc["name"] = _fix_tool_name(tc["name"], tool_names)
            tc["args"] = _normalize_tool_args(tc["args"])

    return {"messages": [response]}


def create_graph(llm: Any, tools: list) -> CompiledStateGraph:
    """Create and compile the ReAct agent graph.

    Graph: prefetch → agent ⇄ tools → END
    """
    tool_names = {t.name for t in tools} if tools else set()
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    graph = StateGraph(AnalyzerState)

    graph.add_node("prefetch", prefetch_node)
    graph.add_node("agent", partial(
        agent_node,
        llm_with_tools=llm_with_tools,
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
