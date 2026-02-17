"""LangGraph CRAG state graph for raid analysis."""

import logging
import re
from functools import partial
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from shukketsu.agent.prompts import (
    ANALYSIS_PROMPT,
    GRADER_PROMPT,
    REWRITE_PROMPT,
    ROUTER_PROMPT,
    SYSTEM_PROMPT,
)
from shukketsu.agent.state import AnalyzerState

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

VALID_QUERY_TYPES = {"my_performance", "comparison", "trend", "general"}

_THINK_PATTERN = re.compile(r"^.*?</think>\s*", flags=re.DOTALL)


def _strip_think_tags(text: str) -> str:
    """Strip Nemotron's leaked reasoning/think tags from output."""
    return _THINK_PATTERN.sub("", text)


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


async def route_query(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    """Classify the user's question type."""
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


async def query_database(state: dict[str, Any], llm_with_tools: Any) -> dict[str, Any]:
    """Use the LLM with tools to query the database based on the question."""
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


async def grade_results(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    """Grade whether the retrieved data is sufficient to answer the question."""
    retry_count = state.get("retry_count", 0)

    # If we've hit max retries, proceed regardless
    if retry_count >= MAX_RETRIES:
        logger.info("Max retries reached, proceeding to analysis")
        return {"grade": "relevant"}

    # Get the last few messages for context
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


async def analyze_results(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    """Analyze the retrieved data and generate insights."""
    messages = [
        SystemMessage(content=f"{SYSTEM_PROMPT}\n\n{ANALYSIS_PROMPT}"),
        *state["messages"],
    ]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


async def generate_insight(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    """Generate the final response with actionable advice."""
    # The analysis step already produced a good response, so we pass it through.
    # If we need extra formatting, this node can refine.
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.content:
        return {}

    # Fallback: generate a response
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
        HumanMessage(content="Please provide a concise, actionable summary."),
    ]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


async def rewrite_query(state: dict[str, Any], llm: Any) -> dict[str, Any]:
    """Reformulate the query when initial retrieval was insufficient."""
    retry_count = state.get("retry_count", 0)
    messages = [
        SystemMessage(content=REWRITE_PROMPT),
        *state["messages"],
    ]
    response = await llm.ainvoke(messages)
    return {
        "messages": [response],
        "retry_count": retry_count + 1,
    }


def _format_messages(messages: list) -> str:
    """Format messages for the grader."""
    parts = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            parts.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            if msg.content:
                parts.append(f"Assistant: {msg.content}")
        elif isinstance(msg, ToolMessage):
            parts.append(f"Tool result: {msg.content}")
    return "\n".join(parts)


def _should_continue(state: dict[str, Any]) -> Literal["analyze", "rewrite"]:
    """Route based on grade result."""
    grade = state.get("grade", "relevant")
    if grade == "insufficient":
        return "rewrite"
    return "analyze"


def create_graph(llm: Any, tools: list) -> Any:
    """Create and compile the CRAG state graph."""
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    graph = StateGraph(AnalyzerState)

    # Add nodes with bound LLM
    graph.add_node("route", partial(route_query, llm=llm))
    graph.add_node("query", partial(query_database, llm_with_tools=llm_with_tools))
    graph.add_node("tool_executor", ToolNode(tools) if tools else _noop_tool_node)
    graph.add_node("grade", partial(grade_results, llm=llm))
    graph.add_node("analyze", partial(analyze_results, llm=llm))
    graph.add_node("respond", partial(generate_insight, llm=llm))
    graph.add_node("rewrite", partial(rewrite_query, llm=llm))

    # Edges
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
    graph.add_edge("analyze", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


def _should_route_to_tools(state: dict[str, Any]) -> Literal["tools", "grade"]:
    """Check if the last message has tool calls."""
    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
    return "grade"


async def _noop_tool_node(state: dict[str, Any]) -> dict[str, Any]:
    """Placeholder when no tools are configured."""
    return {}
