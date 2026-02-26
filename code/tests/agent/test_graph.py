from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from shukketsu.agent.graph import (
    _extract_report_code,
    _fix_tool_name,
    _normalize_tool_args,
    agent_node,
    create_graph,
    prefetch_node,
)

# Valid tool names used across tests
_TOOL_NAMES = {
    "get_my_performance", "get_top_rankings", "compare_to_top",
    "get_fight_details", "get_progression", "get_deaths_and_mechanics",
    "search_fights", "get_spec_leaderboard", "resolve_my_fights",
    "get_wipe_progression", "get_regressions", "compare_raid_to_top",
    "compare_two_raids", "get_raid_execution", "get_ability_breakdown",
    "get_buff_analysis", "get_overheal_analysis", "get_death_analysis",
    "get_activity_report", "get_cooldown_efficiency", "get_cancelled_casts",
    "get_consumable_check", "get_resource_usage", "get_dot_management",
    "get_rotation_score", "get_gear_changes", "get_phase_analysis",
    "get_enchant_gem_check", "get_encounter_benchmarks", "get_spec_benchmark",
}


class TestCreateGraph:
    def test_graph_compiles(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        assert graph is not None

    def test_graph_has_prefetch_agent_and_tools_nodes(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        node_names = set(graph.get_graph().nodes.keys())
        assert "prefetch" in node_names
        assert "agent" in node_names
        assert "tools" in node_names

    def test_graph_does_not_have_crag_nodes(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        node_names = set(graph.get_graph().nodes.keys())
        for old_node in ("route", "query", "grade", "rewrite", "analyze"):
            assert old_node not in node_names

    def test_graph_has_checkpointer(self):
        mock_llm = MagicMock()
        mock_tools = []
        graph = create_graph(mock_llm, mock_tools)
        assert graph.checkpointer is not None


class TestExtractReportCode:
    def test_extracts_32_hex_code(self):
        code = _extract_report_code(
            "Analyze report fb61030ba5a20fd5f51475a7533b57aa"
        )
        assert code == "fb61030ba5a20fd5f51475a7533b57aa"

    def test_extracts_16_char_code(self):
        code = _extract_report_code("report a1B2c3D4e5F6g7H8")
        assert code == "a1B2c3D4e5F6g7H8"

    def test_extracts_from_url(self):
        code = _extract_report_code(
            "https://www.warcraftlogs.com/reports/fb61030ba5a20fd5f51475a7533b57aa"
        )
        assert code == "fb61030ba5a20fd5f51475a7533b57aa"

    def test_returns_none_for_no_code(self):
        assert _extract_report_code("How is my DPS?") is None

    def test_returns_none_for_short_string(self):
        assert _extract_report_code("report abc123") is None


class TestPrefetchNode:
    async def test_prefetches_report_data(self):
        state = {
            "messages": [
                HumanMessage(
                    content="Analyze report fb61030ba5a20fd5f51475a7533b57aa"
                ),
            ]
        }

        mock_tool = AsyncMock()
        mock_tool.ainvoke = AsyncMock(return_value="Raid data: 5 bosses killed")
        with patch(
            "shukketsu.agent.tools.raid_tools.get_raid_execution",
            mock_tool,
        ):
            result = await prefetch_node(state)

        msgs = result.get("messages", [])
        assert len(msgs) == 2
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].tool_calls[0]["name"] == "get_raid_execution"
        assert isinstance(msgs[1], ToolMessage)

    async def test_skips_when_no_report_code(self):
        state = {"messages": [HumanMessage(content="How is my DPS?")]}
        result = await prefetch_node(state)
        assert result == {}

    async def test_skips_when_tool_results_exist(self):
        state = {
            "messages": [
                HumanMessage(
                    content="Analyze report fb61030ba5a20fd5f51475a7533b57aa"
                ),
                AIMessage(content="", tool_calls=[{
                    "name": "get_raid_execution", "args": {}, "id": "1",
                }]),
                ToolMessage(content="data", tool_call_id="1"),
            ]
        }
        result = await prefetch_node(state)
        assert result == {}


class TestAgentNode:
    async def test_prepends_system_message(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Analysis here.")

        state = {"messages": [HumanMessage(content="How is my DPS?")]}
        await agent_node(
            state,
            llm_with_tools=mock_llm,
            tool_names=_TOOL_NAMES,
        )

        call_args = mock_llm.ainvoke.call_args[0][0]
        assert isinstance(call_args[0], SystemMessage)
        assert "Shukketsu" in call_args[0].content

    async def test_returns_ai_message(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Analysis.")

        state = {"messages": [HumanMessage(content="How is my DPS?")]}
        result = await agent_node(
            state,
            llm_with_tools=mock_llm,
            tool_names=_TOOL_NAMES,
        )

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
        result = await agent_node(
            state,
            llm_with_tools=mock_llm,
            tool_names=_TOOL_NAMES,
        )

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
        await agent_node(
            state,
            llm_with_tools=mock_llm,
            tool_names=_TOOL_NAMES,
        )

        call_args = mock_llm.ainvoke.call_args[0][0]
        # SystemMessage + 3 state messages
        assert len(call_args) == 4

    async def test_fixes_hallucinated_tool_name(self):
        """Hallucinated tool names should be fuzzy-matched to valid ones."""
        tool_calls = [
            {"name": "get_analysis", "args": {"report_code": "abc"}, "id": "1"}
        ]
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="", tool_calls=tool_calls
        )

        state = {"messages": [HumanMessage(content="analyze report abc")]}
        result = await agent_node(
            state,
            llm_with_tools=mock_llm,
            tool_names=_TOOL_NAMES,
        )

        fixed_name = result["messages"][0].tool_calls[0]["name"]
        assert fixed_name in _TOOL_NAMES

    async def test_analyzes_prefetched_data(self):
        """After prefetch injects data, agent should receive it and analyze."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="The raid killed 5 bosses with 3 total deaths."
        )

        state = {
            "messages": [
                HumanMessage(content="Analyze report abc123def456ghij"),
                AIMessage(content="", tool_calls=[{
                    "name": "get_raid_execution",
                    "args": {"report_code": "abc123def456ghij"},
                    "id": "prefetch_abc123def456ghij",
                }]),
                ToolMessage(
                    content="Raid Execution Summary: 5 bosses, 3 deaths",
                    tool_call_id="prefetch_abc123def456ghij",
                ),
            ]
        }
        result = await agent_node(
            state,
            llm_with_tools=mock_llm,
            tool_names=_TOOL_NAMES,
        )

        # LLM should produce analysis text, not tool calls
        msg = result["messages"][0]
        assert isinstance(msg, AIMessage)
        assert msg.content  # Has text content
        assert not msg.tool_calls  # No tool calls


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


class TestFixToolName:
    def test_valid_name_unchanged(self):
        assert _fix_tool_name("get_raid_execution", _TOOL_NAMES) == "get_raid_execution"

    def test_camel_case_converted(self):
        assert _fix_tool_name("getMyPerformance", _TOOL_NAMES) == "get_my_performance"

    def test_hallucinated_name_fuzzy_matched(self):
        result = _fix_tool_name("get_death_analys", _TOOL_NAMES)
        assert result == "get_death_analysis"

    def test_completely_wrong_name_returned_as_is(self):
        result = _fix_tool_name("xyzzy_foobar_baz", _TOOL_NAMES)
        assert result == "xyzzy_foobar_baz"

    def test_close_match_for_performance(self):
        result = _fix_tool_name("get_performance", _TOOL_NAMES)
        assert result == "get_my_performance"
