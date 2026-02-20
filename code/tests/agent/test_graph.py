from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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
