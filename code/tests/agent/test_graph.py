from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from shukketsu.agent.graph import (
    _auto_repair_args,
    _extract_player_names,
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

    def test_extracts_15_char_code(self):
        code = _extract_report_code("report xHZ4Vd7WpGBTp7q")
        assert code == "xHZ4Vd7WpGBTp7q"

    def test_extracts_14_char_code(self):
        code = _extract_report_code("report aB3cD4eF5gH6iJ")
        assert code == "aB3cD4eF5gH6iJ"

    def test_rejects_pure_alpha_string(self):
        """English words like 'administration' must not match as report codes."""
        assert _extract_report_code("administration is important") is None
        assert _extract_report_code("Congratulations on the kill") is None
        assert _extract_report_code("characterization of the boss") is None

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

        mock_raid_tool = AsyncMock()
        mock_raid_tool.ainvoke = AsyncMock(
            return_value="Raid data: 5 bosses killed"
        )
        with (
            patch(
                "shukketsu.agent.tools.raid_tools.get_raid_execution",
                mock_raid_tool,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=[],
            ),
        ):
            result = await prefetch_node(state)

        msgs = result.get("messages", [])
        assert len(msgs) >= 2
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].tool_calls[0]["name"] == "get_raid_execution"
        assert isinstance(msgs[1], ToolMessage)
        assert result.get("intent") == "report_analysis"

    async def test_skips_when_no_report_code_and_no_intent(self):
        state = {"messages": [HumanMessage(content="Hello, how are you?")]}
        result = await prefetch_node(state)
        assert result == {}

    async def test_skips_when_tool_results_exist(self):
        """Follow-up turns with existing ToolMessages skip prefetch."""
        state = {
            "messages": [
                HumanMessage(
                    content="Analyze report fb61030ba5a20fd5f51475a7533b57aa"
                ),
                AIMessage(content="", tool_calls=[{
                    "name": "get_raid_execution", "args": {}, "id": "1",
                }]),
                ToolMessage(content="data", tool_call_id="1"),
                HumanMessage(content="Now check Lyroo's rotation"),
            ]
        }
        result = await prefetch_node(state)
        assert result == {}

    async def test_prefetch_report_analysis(self):
        """Report analysis prefetches raid execution + fight details."""
        state = {
            "messages": [
                HumanMessage(
                    content="Analyze report fb61030ba5a20fd5f51475a7533b57aa"
                ),
            ]
        }

        mock_raid = AsyncMock()
        mock_raid.ainvoke = AsyncMock(return_value="raid data")
        mock_details = AsyncMock()
        mock_details.ainvoke = AsyncMock(return_value="fight data")

        with (
            patch(
                "shukketsu.agent.tools.raid_tools.get_raid_execution",
                mock_raid,
            ),
            patch(
                "shukketsu.agent.tools.player_tools.get_fight_details",
                mock_details,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=[8, 10, 12],
            ),
        ):
            result = await prefetch_node(state)

        msgs = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in msgs
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_raid_execution" in tool_names
        assert "get_fight_details" in tool_names
        assert result.get("intent") == "report_analysis"

    async def test_prefetch_player_analysis_fetches_activity_report(self):
        """When intent=player_analysis, prefetch activity_report for kills."""
        msg = HumanMessage(
            content="What could Lyroo do better in Fn2ACKZtyzc1QLJP?"
        )
        mock_raid = AsyncMock()
        mock_raid.ainvoke = AsyncMock(return_value="raid data")
        mock_details = AsyncMock()
        mock_details.ainvoke = AsyncMock(return_value="fight data")
        mock_activity = AsyncMock()
        mock_activity.ainvoke = AsyncMock(return_value="activity data")

        with (
            patch(
                "shukketsu.agent.tools.raid_tools.get_raid_execution",
                mock_raid,
            ),
            patch(
                "shukketsu.agent.tools.player_tools.get_fight_details",
                mock_details,
            ),
            patch(
                "shukketsu.agent.tools.event_tools.get_activity_report",
                mock_activity,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=[8, 10, 12],
            ),
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_raid_execution" in tool_names
        assert "get_fight_details" in tool_names
        assert "get_activity_report" in tool_names
        assert result.get("intent") == "player_analysis"

    async def test_prefetch_benchmarks(self):
        """When intent=benchmarks, prefetch encounter benchmarks."""
        msg = HumanMessage(
            content="Show me encounter benchmarks for Gruul the Dragonkiller"
        )
        mock_bench = AsyncMock()
        mock_bench.ainvoke = AsyncMock(return_value="benchmark data")

        with patch(
            "shukketsu.agent.tools.benchmark_tools.get_encounter_benchmarks",
            mock_bench,
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_encounter_benchmarks" in tool_names
        assert result.get("intent") == "benchmarks"

    async def test_prefetch_specific_tool_with_report(self):
        """Specific tool + report code → prefetch resolves fight and calls it."""
        msg = HumanMessage(
            content="Pull a rotation score for Lyroo on Fn2ACKZtyzc1QLJP"
        )
        mock_rotation = AsyncMock()
        mock_rotation.ainvoke = AsyncMock(return_value="rotation data")

        with (
            patch(
                "shukketsu.agent.tools.event_tools.get_rotation_score",
                mock_rotation,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=[8, 10],
            ),
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_rotation_score" in tool_names
        assert result.get("intent") == "specific_tool"

    async def test_prefetch_progression(self):
        """When intent=progression, prefetch get_progression."""
        msg = HumanMessage(content="Show me Lyroo's progression over time")
        mock_prog = AsyncMock()
        mock_prog.ainvoke = AsyncMock(return_value="progression data")

        with patch(
            "shukketsu.agent.tools.player_tools.get_progression",
            mock_prog,
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_progression" in tool_names
        assert result.get("intent") == "progression"

    async def test_prefetch_leaderboard(self):
        """When intent=leaderboard, prefetch spec_leaderboard."""
        msg = HumanMessage(content="What specs top DPS on Gruul?")
        mock_lb = AsyncMock()
        mock_lb.ainvoke = AsyncMock(return_value="leaderboard data")

        with patch(
            "shukketsu.agent.tools.player_tools.get_spec_leaderboard",
            mock_lb,
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_spec_leaderboard" in tool_names
        assert result.get("intent") == "leaderboard"

    async def test_prefetch_compare_to_top(self):
        """When intent=compare_to_top with report, prefetch compare_raid."""
        msg = HumanMessage(
            content="How does our raid compare to top guilds? "
            "Report Fn2ACKZtyzc1QLJP"
        )
        mock_compare = AsyncMock()
        mock_compare.ainvoke = AsyncMock(return_value="comparison data")

        with patch(
            "shukketsu.agent.tools.raid_tools.compare_raid_to_top",
            mock_compare,
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "compare_raid_to_top" in tool_names
        assert result.get("intent") == "compare_to_top"

    async def test_prefetch_caps_fight_details_at_max(self):
        """Prefetch should not fetch more than MAX_PREFETCH_FIGHTS fights."""
        from shukketsu.agent.graph import _MAX_PREFETCH_FIGHTS

        state = {
            "messages": [
                HumanMessage(
                    content="Analyze report fb61030ba5a20fd5f51475a7533b57aa"
                ),
            ]
        }
        mock_raid = AsyncMock()
        mock_raid.ainvoke = AsyncMock(return_value="raid data")
        mock_details = AsyncMock()
        mock_details.ainvoke = AsyncMock(return_value="fight data")

        many_fights = list(range(1, 15))  # 14 fights
        with (
            patch(
                "shukketsu.agent.tools.raid_tools.get_raid_execution",
                mock_raid,
            ),
            patch(
                "shukketsu.agent.tools.player_tools.get_fight_details",
                mock_details,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=many_fights,
            ),
        ):
            result = await prefetch_node(state)

        # Count get_fight_details calls
        detail_calls = [
            m for m in result["messages"]
            if hasattr(m, "tool_calls") and m.tool_calls
            and m.tool_calls[0]["name"] == "get_fight_details"
        ]
        assert len(detail_calls) == _MAX_PREFETCH_FIGHTS

    async def test_prefetch_specific_uses_user_fight_id(self):
        """When user specifies fight_id, prefetch uses it instead of DB lookup."""
        msg = HumanMessage(
            content="Show death analysis for Gruul in Fn2ACKZtyzc1QLJP fight 8"
        )
        mock_death = AsyncMock()
        mock_death.ainvoke = AsyncMock(return_value="death data")

        with (
            patch(
                "shukketsu.agent.tools.event_tools.get_death_analysis",
                mock_death,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=[3, 5, 8],
            ) as mock_kill_ids,
        ):
            await prefetch_node({"messages": [msg]})

        # Should NOT have called _get_kill_fight_ids since user specified fight 8
        mock_kill_ids.assert_not_called()
        # Tool should have been called with fight_id=8
        mock_death.ainvoke.assert_called_once()
        call_args = mock_death.ainvoke.call_args[0][0]
        assert call_args["fight_id"] == 8

    async def test_prefetch_specific_failure_injects_hint(self):
        """When prefetch tool fails, inject a hint so LLM knows what to try."""
        msg = HumanMessage(
            content="Show wipe progression for Prince in xHZ4Vd7WpGBTp7q"
        )
        mock_wipe = AsyncMock()
        mock_wipe.ainvoke = AsyncMock(side_effect=Exception("No data"))

        with patch(
            "shukketsu.agent.tools.player_tools.get_wipe_progression",
            mock_wipe,
        ):
            result = await prefetch_node({"messages": [msg]})

        # Should still return the intent
        assert result.get("intent") == "specific_tool"
        # Should have injected messages with a hint about what was tried
        msgs = result.get("messages", [])
        assert len(msgs) > 0
        # At least one message should mention the tool name
        all_content = " ".join(
            m.content for m in msgs
            if hasattr(m, "content") and isinstance(m.content, str)
        )
        assert "get_wipe_progression" in all_content

    async def test_prefetch_gear_changes_uses_two_report_codes(self):
        """Gear compare with 2 report codes → report_code_old + report_code_new."""
        msg = HumanMessage(
            content="Compare Arrowstorm's gear between "
            "wX1yZ3aB5cD7eF9g and Hy7KmN9pQ2rS4tU6"
        )
        mock_gear = AsyncMock()
        mock_gear.ainvoke = AsyncMock(return_value="gear diff data")

        with patch(
            "shukketsu.agent.tools.event_tools.get_gear_changes",
            mock_gear,
        ):
            result = await prefetch_node({"messages": [msg]})

        assert result.get("intent") == "specific_tool"
        # Tool should be called with report_code_old and report_code_new
        mock_gear.ainvoke.assert_called_once()
        call_args = mock_gear.ainvoke.call_args[0][0]
        assert call_args["report_code_old"] == "wX1yZ3aB5cD7eF9g"
        assert call_args["report_code_new"] == "Hy7KmN9pQ2rS4tU6"
        assert "report_code" not in call_args
        assert call_args["player_name"] == "Arrowstorm"

    async def test_prefetch_compare_two_raids(self):
        """Compare intent with 2 report codes → compare_two_raids."""
        msg = HumanMessage(
            content="Compare report wX1yZ3aB5cD7eF9g to report Hy7KmN9pQ2rS4tU6"
        )
        mock_compare = AsyncMock()
        mock_compare.ainvoke = AsyncMock(return_value="comparison data")

        with patch(
            "shukketsu.agent.tools.raid_tools.compare_two_raids",
            mock_compare,
        ):
            result = await prefetch_node({"messages": [msg]})

        assert result.get("intent") == "compare_to_top"
        mock_compare.ainvoke.assert_called_once()
        call_args = mock_compare.ainvoke.call_args[0][0]
        assert call_args["report_a"] == "wX1yZ3aB5cD7eF9g"
        assert call_args["report_b"] == "Hy7KmN9pQ2rS4tU6"

    async def test_prefetch_specific_error_includes_player_reminder(self):
        """When tool returns error string, append player name reminder."""
        msg = HumanMessage(
            content="Show death recap for Tankboy in fight 21 of "
            "fb61030ba5a20fd5f51475a7533b57aa"
        )
        mock_death = AsyncMock()
        mock_death.ainvoke = AsyncMock(
            return_value="Error: No data found for this report"
        )

        with patch(
            "shukketsu.agent.tools.event_tools.get_death_analysis",
            mock_death,
        ):
            result = await prefetch_node({"messages": [msg]})

        # The injected ToolMessage should contain the player name reminder
        msgs = result.get("messages", [])
        tool_content = " ".join(
            m.content for m in msgs
            if isinstance(m, ToolMessage)
        )
        assert "Tankboy" in tool_content

    async def test_prefetch_specific_without_report_code(self):
        """Specific tool without report code → call tool with available args."""
        msg = HumanMessage(content="Check for performance regressions")
        mock_reg = AsyncMock()
        mock_reg.ainvoke = AsyncMock(return_value="regression data")

        with patch(
            "shukketsu.agent.tools.player_tools.get_regressions",
            mock_reg,
        ):
            result = await prefetch_node({"messages": [msg]})

        messages = result["messages"]
        tool_names = [
            m.tool_calls[0]["name"]
            for m in messages
            if hasattr(m, "tool_calls") and m.tool_calls
        ]
        assert "get_regressions" in tool_names

    async def test_prefetch_returns_player_names(self):
        """Prefetch should set player_names in state for agent_node to use."""
        msg = HumanMessage(
            content="Show Tankboy's death recap in Fn2ACKZtyzc1QLJP"
        )
        mock_death = AsyncMock()
        mock_death.ainvoke = AsyncMock(return_value="death data")

        with (
            patch(
                "shukketsu.agent.tools.event_tools.get_death_analysis",
                mock_death,
            ),
            patch(
                "shukketsu.agent.graph._get_kill_fight_ids",
                return_value=[8],
            ),
        ):
            result = await prefetch_node({"messages": [msg]})

        assert "player_names" in result
        assert "Tankboy" in result["player_names"]


class TestAgentNode:
    async def test_prepends_system_message(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Analysis here.")

        state = {"messages": [HumanMessage(content="How is my DPS?")]}
        await agent_node(
            state,
            llm=mock_llm,
            all_tools=[],
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
            llm=mock_llm,
            all_tools=[],
            tool_names=_TOOL_NAMES,
        )

        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    async def test_normalizes_pascal_case_tool_args(self):
        tool_calls = [
            {
                "name": "get_my_performance",
                "args": {"EncounterName": "Gruul"},
                "id": "1",
            }
        ]
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="", tool_calls=tool_calls
        )

        state = {"messages": [HumanMessage(content="My DPS on Gruul?")]}
        result = await agent_node(
            state,
            llm=mock_llm,
            all_tools=[],
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
                    tool_calls=[{
                        "name": "get_my_performance", "args": {}, "id": "1",
                    }],
                ),
                ToolMessage(content="DPS: 1500", tool_call_id="1"),
            ]
        }
        await agent_node(
            state,
            llm=mock_llm,
            all_tools=[],
            tool_names=_TOOL_NAMES,
        )

        call_args = mock_llm.ainvoke.call_args[0][0]
        # SystemMessage + 3 state messages
        assert len(call_args) == 4

    async def test_fixes_hallucinated_tool_name(self):
        """Hallucinated tool names should be fuzzy-matched to valid ones."""
        tool_calls = [
            {
                "name": "get_analysis",
                "args": {"report_code": "abc"},
                "id": "1",
            }
        ]
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="", tool_calls=tool_calls
        )

        state = {"messages": [HumanMessage(content="analyze report abc")]}
        result = await agent_node(
            state,
            llm=mock_llm,
            all_tools=[],
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
            llm=mock_llm,
            all_tools=[],
            tool_names=_TOOL_NAMES,
        )

        msg = result["messages"][0]
        assert isinstance(msg, AIMessage)
        assert msg.content
        assert not msg.tool_calls


class TestToolArgNormalization:
    def test_normalize_converts_pascal_to_snake(self):
        args = {
            "EncounterName": "Gruul the Dragonkiller",
            "PlayerName": "Lyro",
        }
        result = _normalize_tool_args(args)
        assert result == {
            "encounter_name": "Gruul the Dragonkiller",
            "player_name": "Lyro",
        }

    def test_normalize_preserves_snake_case(self):
        args = {
            "encounter_name": "Gruul the Dragonkiller",
            "player_name": "Lyro",
        }
        result = _normalize_tool_args(args)
        assert result == {
            "encounter_name": "Gruul the Dragonkiller",
            "player_name": "Lyro",
        }

    def test_normalize_handles_mixed_case(self):
        args = {"ClassName": "Warrior", "spec_name": "Arms"}
        result = _normalize_tool_args(args)
        assert result == {"class_name": "Warrior", "spec_name": "Arms"}


class TestNormalizeToolArgs:
    """Tests for _normalize_tool_args with alias map and type coercion."""

    def test_pascal_case_conversion(self):
        result = _normalize_tool_args({"EncounterName": "Gruul"})
        assert result == {"encounter_name": "Gruul"}

    def test_alias_term_to_encounter_name(self):
        result = _normalize_tool_args({"term": "Gruul"})
        assert result == {"encounter_name": "Gruul"}

    def test_alias_reportcode(self):
        result = _normalize_tool_args({"reportcode": "ABC123"})
        assert result == {"report_code": "ABC123"}

    def test_alias_report_id(self):
        result = _normalize_tool_args({"report_id": "ABC123"})
        assert result == {"report_code": "ABC123"}

    def test_alias_playername(self):
        result = _normalize_tool_args({"playername": "Lyroo"})
        assert result == {"player_name": "Lyroo"}

    def test_unknown_key_name_kept_as_is(self):
        """'name' is too ambiguous to alias — keep it for the LLM to handle."""
        result = _normalize_tool_args({"name": "Lyroo"})
        assert result == {"name": "Lyroo"}

    def test_alias_is_id(self):
        result = _normalize_tool_args({"is_id": "ABC123"})
        assert result == {"report_code": "ABC123"}

    def test_fight_id_string_to_int(self):
        result = _normalize_tool_args({"fight_id": "8"})
        assert result == {"fight_id": 8}

    def test_fight_id_int_unchanged(self):
        result = _normalize_tool_args({"fight_id": 8})
        assert result == {"fight_id": 8}

    def test_combined_fixes(self):
        """PascalCase + alias + type coercion all at once."""
        result = _normalize_tool_args({
            "ReportCode": "ABC123",
            "FightId": "8",
            "PlayerName": "Lyroo",
        })
        assert result == {
            "report_code": "ABC123",
            "fight_id": 8,
            "player_name": "Lyroo",
        }

    def test_alias_boss_to_encounter_name(self):
        result = _normalize_tool_args({"boss": "Gruul"})
        assert result == {"encounter_name": "Gruul"}

    def test_alias_encounter_to_encounter_name(self):
        result = _normalize_tool_args({"encounter": "Gruul"})
        assert result == {"encounter_name": "Gruul"}

    def test_character_name_preserved(self):
        """character_name should NOT be aliased to player_name."""
        result = _normalize_tool_args({"character_name": "Lyroo"})
        assert result == {"character_name": "Lyroo"}

    def test_bests_only_string_to_bool(self):
        result = _normalize_tool_args({"bests_only": "true"})
        assert result == {"bests_only": True}

    def test_bests_only_false_string(self):
        result = _normalize_tool_args({"bests_only": "false"})
        assert result == {"bests_only": False}

    def test_count_string_to_int(self):
        result = _normalize_tool_args({"count": "10"})
        assert result == {"count": 10}

    def test_invalid_int_string_unchanged(self):
        result = _normalize_tool_args({"fight_id": "not_a_number"})
        assert result == {"fight_id": "not_a_number"}

    def test_report_code_hash_suffix_stripped(self):
        """LLM sometimes appends #fight_id to report_code — strip it."""
        result = _normalize_tool_args({
            "report_code": "Fn2ACKZtyzc1QLJP#3",
        })
        assert result["report_code"] == "Fn2ACKZtyzc1QLJP"
        # fight_id is also extracted from the #N suffix
        assert result["fight_id"] == 3

    def test_report_code_hash_suffix_extracts_fight_id(self):
        """When report_code has #N, extract fight_id if not already present."""
        result = _normalize_tool_args({
            "report_code": "Fn2ACKZtyzc1QLJP#8",
        })
        assert result == {"report_code": "Fn2ACKZtyzc1QLJP", "fight_id": 8}

    def test_report_code_hash_no_clobber_fight_id(self):
        """Don't overwrite an existing fight_id from the #N extraction."""
        result = _normalize_tool_args({
            "report_code": "Fn2ACKZtyzc1QLJP#3",
            "fight_id": 8,
        })
        assert result == {
            "report_code": "Fn2ACKZtyzc1QLJP",
            "fight_id": 8,
        }

    def test_clean_report_code_untouched(self):
        """Report codes without # suffix are preserved."""
        result = _normalize_tool_args({
            "report_code": "Fn2ACKZtyzc1QLJP",
        })
        assert result == {"report_code": "Fn2ACKZtyzc1QLJP"}


class TestFixToolName:
    def test_valid_name_unchanged(self):
        assert (
            _fix_tool_name("get_raid_execution", _TOOL_NAMES)
            == "get_raid_execution"
        )

    def test_camel_case_converted(self):
        assert (
            _fix_tool_name("getMyPerformance", _TOOL_NAMES)
            == "get_my_performance"
        )

    def test_hallucinated_name_fuzzy_matched(self):
        result = _fix_tool_name("get_death_analys", _TOOL_NAMES)
        assert result == "get_death_analysis"

    def test_completely_wrong_name_returned_as_is(self):
        result = _fix_tool_name("xyzzy_foobar_baz", _TOOL_NAMES)
        assert result == "xyzzy_foobar_baz"

    def test_close_match_for_performance(self):
        result = _fix_tool_name("get_performance", _TOOL_NAMES)
        assert result == "get_my_performance"

    # Alias map tests (Task 6)
    def test_alias_analyze_report(self):
        assert (
            _fix_tool_name("analyze_report", _TOOL_NAMES)
            == "get_raid_execution"
        )

    def test_alias_get_analysis(self):
        assert _fix_tool_name("get_analysis", _TOOL_NAMES) in {
            "get_raid_execution", "get_activity_report",
        }

    def test_alias_get_analysis_metrics(self):
        assert (
            _fix_tool_name("get_analysis_metrics", _TOOL_NAMES)
            == "get_activity_report"
        )

    def test_alias_search(self):
        assert (
            _fix_tool_name("search", _TOOL_NAMES) == "search_fights"
        )

    def test_alias_get_character_profile(self):
        assert (
            _fix_tool_name("get_character_profile", _TOOL_NAMES)
            == "get_progression"
        )

    def test_alias_get_report(self):
        assert (
            _fix_tool_name("get_report", _TOOL_NAMES)
            == "get_raid_execution"
        )

    def test_alias_get_player_performance(self):
        assert (
            _fix_tool_name("get_player_performance", _TOOL_NAMES)
            == "get_my_performance"
        )

    def test_alias_pull_table_data(self):
        """LLM sometimes hallucinates CLI script name pull_table_data."""
        assert (
            _fix_tool_name("pull_table_data", _TOOL_NAMES)
            == "get_ability_breakdown"
        )

    def test_alias_pull_rankings(self):
        """LLM sometimes hallucinates CLI script name pull_rankings."""
        assert (
            _fix_tool_name("pull_rankings", _TOOL_NAMES)
            == "get_top_rankings"
        )

    def test_alias_get_report_data(self):
        """LLM sometimes hallucinates get_report_data."""
        assert (
            _fix_tool_name("get_report_data", _TOOL_NAMES)
            == "get_raid_execution"
        )


class TestExtractPlayerNames:
    def test_extracts_player_name(self):
        names = _extract_player_names("what could Lyroo have done better")
        assert "Lyroo" in names

    def test_ignores_common_words(self):
        names = _extract_player_names("Can you Please Analyze the Report")
        assert names == []

    def test_ignores_boss_names(self):
        names = _extract_player_names(
            "How did we do on Gruul and Magtheridon"
        )
        assert names == []

    def test_extracts_multiple_names(self):
        names = _extract_player_names("Compare Lyroo and Tankboy on Gruul")
        assert "Lyroo" in names
        assert "Tankboy" in names
        assert "Gruul" not in names


class TestContextualToolFiltering:
    def test_report_analysis_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent("report_analysis", mock_tools)
        names = {t.name for t in tools}
        assert "get_deaths_and_mechanics" in names
        assert "get_encounter_benchmarks" in names
        assert "search_fights" in names
        assert len(names) <= 12

    def test_player_analysis_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent("player_analysis", mock_tools)
        names = {t.name for t in tools}
        assert "get_activity_report" in names
        assert "compare_to_top" in names
        assert len(names) <= 12

    def test_benchmarks_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent("benchmarks", mock_tools)
        names = {t.name for t in tools}
        assert "get_encounter_benchmarks" in names
        assert "get_spec_benchmark" in names
        assert len(names) <= 6

    def test_unknown_intent_gets_all_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent(None, mock_tools)
        assert len(tools) == len(_TOOL_NAMES)

    def test_specific_tool_gets_all_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent("specific_tool", mock_tools)
        assert len(tools) == len(_TOOL_NAMES)

    def test_compare_to_top_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent("compare_to_top", mock_tools)
        names = {t.name for t in tools}
        assert "compare_raid_to_top" in names
        assert "get_encounter_benchmarks" in names

    def test_progression_tools(self):
        from shukketsu.agent.graph import _get_tools_for_intent

        mock_tools = [MagicMock(name=n) for n in _TOOL_NAMES]
        for t, n in zip(mock_tools, _TOOL_NAMES, strict=True):
            t.name = n

        tools = _get_tools_for_intent("progression", mock_tools)
        names = {t.name for t in tools}
        assert "get_progression" in names
        assert "get_regressions" in names


class TestAutoRepairArgs:
    """Tests for _auto_repair_args filling missing args from conversation."""

    def test_fills_missing_report_code_from_messages(self):
        messages = [
            HumanMessage(content="Analyze report Fn2ACKZtyzc1QLJP"),
            AIMessage(content="data"),
        ]
        args = {"fight_id": 8, "player_name": "Lyroo"}
        repaired = _auto_repair_args("get_activity_report", args, messages)
        assert repaired["report_code"] == "Fn2ACKZtyzc1QLJP"

    def test_fills_missing_player_name_from_messages(self):
        messages = [
            HumanMessage(
                content="What could Lyroo do better in Fn2ACKZtyzc1QLJP?"
            ),
        ]
        args = {"report_code": "Fn2ACKZtyzc1QLJP", "fight_id": 8}
        repaired = _auto_repair_args("get_activity_report", args, messages)
        assert repaired["player_name"] == "Lyroo"

    def test_fills_missing_encounter_name_from_messages(self):
        messages = [
            HumanMessage(content="Show me the benchmarks for Gruul"),
        ]
        args = {}
        repaired = _auto_repair_args(
            "get_encounter_benchmarks", args, messages,
        )
        assert "gruul" in repaired.get("encounter_name", "").lower()

    def test_does_not_overwrite_existing_args(self):
        messages = [
            HumanMessage(content="Check Flasheal in Fn2ACKZtyzc1QLJP"),
        ]
        args = {
            "report_code": "Fn2ACKZtyzc1QLJP",
            "fight_id": 8,
            "player_name": "Lyroo",
        }
        repaired = _auto_repair_args("get_activity_report", args, messages)
        assert repaired["player_name"] == "Lyroo"  # not overwritten

    def test_no_repair_when_nothing_to_extract(self):
        messages = [HumanMessage(content="Hello")]
        args = {"fight_id": 8}
        repaired = _auto_repair_args("get_activity_report", args, messages)
        assert "report_code" not in repaired

    def test_extracts_from_prior_tool_results(self):
        """Should find report codes in ToolMessage content too."""
        messages = [
            HumanMessage(content="analyze this report"),
            AIMessage(content="", tool_calls=[{
                "name": "get_raid_execution",
                "args": {"report_code": "Fn2ACKZtyzc1QLJP"},
                "id": "1",
            }]),
            ToolMessage(
                content="Raid Fn2ACKZtyzc1QLJP: 5 kills",
                tool_call_id="1",
            ),
            HumanMessage(content="Now check Lyroo's cooldowns"),
        ]
        args = {"fight_id": 8}
        repaired = _auto_repair_args(
            "get_cooldown_efficiency", args, messages,
        )
        assert repaired["report_code"] == "Fn2ACKZtyzc1QLJP"
        assert repaired["player_name"] == "Lyroo"

    def test_extracts_from_prior_tool_call_args(self):
        """Should find args from prior AIMessage tool_calls."""
        messages = [
            HumanMessage(content="analyze this"),
            AIMessage(content="", tool_calls=[{
                "name": "get_raid_execution",
                "args": {"report_code": "Fn2ACKZtyzc1QLJP"},
                "id": "1",
            }]),
            ToolMessage(content="data", tool_call_id="1"),
            HumanMessage(content="Now check Lyroo"),
        ]
        args = {"fight_id": 8}
        repaired = _auto_repair_args(
            "get_activity_report", args, messages,
        )
        assert repaired["report_code"] == "Fn2ACKZtyzc1QLJP"


class TestRetryBudget:
    """Tests for retry budget with escalating hints and graceful fallback."""

    async def test_error_detected_increments_count(self):
        """After a tool error, tool_error_count should increase."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="",
            tool_calls=[{
                "name": "search_fights",
                "args": {"encounter_name": "Gruul"},
                "id": "2",
            }],
        )

        state = {
            "messages": [
                HumanMessage(content="Search for Gruul"),
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "search_fights",
                        "args": {},
                        "id": "1",
                    }],
                ),
                ToolMessage(
                    content="Error: encounter_name: Field required",
                    tool_call_id="1",
                ),
            ],
            "tool_error_count": 0,
        }
        result = await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )
        assert result.get("tool_error_count", 0) == 1

    async def test_retry_hint_injected_on_error(self):
        """Agent should see a retry hint when a tool error occurred."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="retrying...")

        state = {
            "messages": [
                HumanMessage(content="Search for Gruul"),
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "search_fights",
                        "args": {},
                        "id": "1",
                    }],
                ),
                ToolMessage(
                    content="Error: encounter_name: Field required",
                    tool_call_id="1",
                ),
            ],
            "tool_error_count": 0,
        }
        await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        # Check that the LLM received a retry hint (separate from SYSTEM_PROMPT)
        call_args = mock_llm.ainvoke.call_args[0][0]
        # Count SystemMessages — should have SYSTEM_PROMPT + retry hint = 2
        sys_msgs = [m for m in call_args if isinstance(m, SystemMessage)]
        assert len(sys_msgs) == 2
        retry_hint = sys_msgs[1]
        assert "failed" in retry_hint.content.lower()

    async def test_graceful_fallback_after_3_errors(self):
        """After 3 errors, agent should return a fallback message, not retry."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="",
            tool_calls=[{
                "name": "search_fights",
                "args": {},
                "id": "4",
            }],
        )

        state = {
            "messages": [
                HumanMessage(content="Search for Gruul"),
                ToolMessage(
                    content="Error: something broke",
                    tool_call_id="3",
                ),
            ],
            "tool_error_count": 3,
        }
        result = await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        msg = result["messages"][0]
        assert isinstance(msg, AIMessage)
        assert not msg.tool_calls  # no more tool calls
        assert "wasn't able" in msg.content.lower()

    async def test_no_hint_when_no_error(self):
        """Normal responses should not get extra hint SystemMessages."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(content="Analysis here.")

        state = {
            "messages": [
                HumanMessage(content="How is my DPS?"),
            ],
            "tool_error_count": 0,
        }
        await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        call_args = mock_llm.ainvoke.call_args[0][0]
        # Only the SYSTEM_PROMPT SystemMessage should be present
        sys_msgs = [m for m in call_args if isinstance(m, SystemMessage)]
        assert len(sys_msgs) == 1

    async def test_error_count_resets_on_success(self):
        """When tool returns non-error data, count should reset."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="Gruul analysis here."
        )

        state = {
            "messages": [
                HumanMessage(content="Analyze Gruul"),
                AIMessage(content="", tool_calls=[{
                    "name": "search_fights",
                    "args": {"encounter_name": "Gruul"},
                    "id": "1",
                }]),
                ToolMessage(
                    content="Fight data for Gruul: ...",
                    tool_call_id="1",
                ),
            ],
            "tool_error_count": 2,
        }
        result = await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        assert result.get("tool_error_count", 0) == 0

    async def test_player_focus_system_message_on_tool_error(self):
        """When tool error + player_names in state, inject player focus hint."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="Analysis for Zapzap."
        )

        state = {
            "messages": [
                HumanMessage(content="Show death recap for Zapzap"),
                AIMessage(content="", tool_calls=[{
                    "name": "get_death_analysis",
                    "args": {"player_name": "Zapzap", "report_code": "abc"},
                    "id": "1",
                }]),
                ToolMessage(
                    content="Error: No death data found.",
                    tool_call_id="1",
                ),
            ],
            "player_names": ["Zapzap"],
            "tool_error_count": 0,
        }
        await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        # Should have injected a SystemMessage mentioning the player name
        call_args = mock_llm.ainvoke.call_args[0][0]
        sys_msgs = [m for m in call_args if isinstance(m, SystemMessage)]
        # Must have a separate SystemMessage (not SYSTEM_PROMPT) with player name
        player_msgs = [
            m for m in sys_msgs
            if "Zapzap" in m.content
        ]
        assert len(player_msgs) >= 1, (
            "Expected SystemMessage mentioning Zapzap"
        )

    async def test_player_name_injected_into_response_when_missing(self):
        """When player_names set but model omits them, prepend to response."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="No death data found for fight 21."
        )

        state = {
            "messages": [
                HumanMessage(content="Show death recap for Zapzap"),
                AIMessage(content="", tool_calls=[{
                    "name": "get_death_analysis",
                    "args": {"player_name": "Zapzap", "report_code": "abc"},
                    "id": "1",
                }]),
                ToolMessage(
                    content="Error: No death data found.",
                    tool_call_id="1",
                ),
            ],
            "player_names": ["Zapzap"],
            "tool_error_count": 0,
        }
        result = await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        response = result["messages"][0]
        assert "Zapzap" in response.content

    async def test_player_name_not_duplicated_when_present(self):
        """When model already mentions the player, don't prepend."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="Zapzap's death data is not available."
        )

        state = {
            "messages": [HumanMessage(content="test")],
            "player_names": ["Zapzap"],
        }
        result = await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        response = result["messages"][0]
        # Should NOT have "Regarding Zapzap:" prefix
        assert not response.content.startswith("Regarding")

    async def test_no_player_focus_msg_without_player_names(self):
        """No player focus hint when player_names not in state."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AIMessage(
            content="Analysis."
        )

        state = {
            "messages": [
                HumanMessage(content="Analyze Gruul"),
                AIMessage(content="", tool_calls=[{
                    "name": "search_fights",
                    "args": {"encounter_name": "Gruul"},
                    "id": "1",
                }]),
                ToolMessage(
                    content="Error: No data found.",
                    tool_call_id="1",
                ),
            ],
            "tool_error_count": 0,
        }
        await agent_node(
            state, llm=mock_llm, all_tools=[], tool_names=_TOOL_NAMES,
        )

        # Only SYSTEM_PROMPT + retry hint, no player focus message
        call_args = mock_llm.ainvoke.call_args[0][0]
        sys_msgs = [m for m in call_args if isinstance(m, SystemMessage)]
        # Should be exactly 2: SYSTEM_PROMPT + retry hint
        assert len(sys_msgs) == 2
