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
