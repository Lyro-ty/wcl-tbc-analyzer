from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from shukketsu.agent.graph import (
    MAX_RETRIES,
    _format_messages,
    create_graph,
    grade_results,
    route_query,
)


class TestCreateGraph:
    def test_graph_compiles(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        assert graph is not None

    def test_graph_has_nodes(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        node_names = set(graph.get_graph().nodes.keys())
        # LangGraph adds __start__ and __end__ nodes
        assert "route" in node_names
        assert "query" in node_names
        assert "grade" in node_names
        assert "analyze" in node_names
        assert "respond" in node_names
        assert "rewrite" in node_names


class TestRouteQuery:
    async def test_classifies_my_performance(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="my_performance")

        state = {
            "messages": [HumanMessage(content="Why is my DPS low on Gruul?")],
        }
        result = await route_query(state, mock_llm)
        assert result["query_type"] == "my_performance"

    async def test_classifies_comparison(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="comparison")

        state = {
            "messages": [HumanMessage(content="How do I compare to top rogues?")],
        }
        result = await route_query(state, mock_llm)
        assert result["query_type"] == "comparison"

    async def test_defaults_to_general(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="something_invalid")

        state = {
            "messages": [HumanMessage(content="Tell me about Gruul")],
        }
        result = await route_query(state, mock_llm)
        assert result["query_type"] == "general"


class TestGradeResults:
    async def test_relevant_returns_analyze(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="relevant")

        state = {
            "messages": [
                HumanMessage(content="Show my parses"),
                AIMessage(content="Performance data: DPS 1500, Parse 95%"),
            ],
            "retry_count": 0,
        }
        result = await grade_results(state, mock_llm)
        assert result["grade"] == "relevant"

    async def test_insufficient_returns_rewrite(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="insufficient")

        state = {
            "messages": [
                HumanMessage(content="Show my parses"),
                AIMessage(content="No data found."),
            ],
            "retry_count": 0,
        }
        result = await grade_results(state, mock_llm)
        assert result["grade"] == "insufficient"

    async def test_max_retries_forces_relevant(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="insufficient")

        state = {
            "messages": [
                HumanMessage(content="Show my parses"),
                AIMessage(content="No data found."),
            ],
            "retry_count": MAX_RETRIES,
        }
        result = await grade_results(state, mock_llm)
        # Should proceed to analyze even if insufficient, to avoid infinite loop
        assert result["grade"] == "relevant"


class TestFormatMessages:
    def test_includes_tool_message(self):
        messages = [
            HumanMessage(content="Show my parses"),
            AIMessage(
                content="",
                tool_calls=[{"name": "get_my_performance", "args": {}, "id": "1"}],
            ),
            ToolMessage(content="DPS: 1500, Parse: 95%", tool_call_id="1"),
        ]
        result = _format_messages(messages)
        assert "Tool result: DPS: 1500, Parse: 95%" in result

    def test_skips_empty_ai_content(self):
        messages = [
            HumanMessage(content="question"),
            AIMessage(content=""),
        ]
        result = _format_messages(messages)
        assert "Assistant:" not in result

    def test_includes_ai_with_content(self):
        messages = [
            AIMessage(content="Here is your data"),
        ]
        result = _format_messages(messages)
        assert "Assistant: Here is your data" in result

    def test_all_message_types(self):
        messages = [
            HumanMessage(content="query"),
            AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
            ToolMessage(content="result data", tool_call_id="1"),
            AIMessage(content="Analysis complete"),
        ]
        result = _format_messages(messages)
        assert "User: query" in result
        assert "Tool result: result data" in result
        assert "Assistant: Analysis complete" in result


class TestMaxRetries:
    def test_max_retries_is_two(self):
        assert MAX_RETRIES == 2
