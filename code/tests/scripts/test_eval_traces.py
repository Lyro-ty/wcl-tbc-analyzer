"""Tests for the eval_traces scoring functions."""

from shukketsu.scripts.eval_traces import score_trace


class TestScoreTrace:
    """Tests for the score_trace function."""

    def test_valid_tool_call_scores_perfectly(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_spec_leaderboard",
                        "arguments": {"encounter_name": "Gruul the Dragonkiller"},
                    }
                ],
            },
            {"role": "assistant", "content": "Top DPS on Gruul: Destro Lock."},
        ]
        scores = score_trace(messages, "What specs top DPS on Gruul?")
        assert scores["tool_name_accuracy"] == 1.0
        assert scores["arg_accuracy"] == 1.0
        assert scores["depth"] == 1
        assert scores["no_give_up"] == 1.0

    def test_invalid_tool_name_scores_zero(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_dps_rankings",  # not a valid tool
                        "arguments": {"encounter_name": "Gruul"},
                    }
                ],
            },
            {"role": "assistant", "content": "Analysis complete."},
        ]
        scores = score_trace(messages, "top DPS?")
        assert scores["tool_name_accuracy"] == 0.0

    def test_invalid_arg_name_scores_zero(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_spec_leaderboard",
                        "arguments": {"boss_name": "Gruul"},  # wrong arg name
                    }
                ],
            },
            {"role": "assistant", "content": "Analysis."},
        ]
        scores = score_trace(messages, "top DPS?")
        assert scores["arg_accuracy"] == 0.0

    def test_no_tool_calls_depth_zero(self):
        messages = [
            {"role": "assistant", "content": "I don't know."},
        ]
        scores = score_trace(messages, "What DPS on Gruul?")
        assert scores["depth"] == 0
        assert scores["tool_name_accuracy"] == 0.0

    def test_give_up_phrase_detected(self):
        messages = [
            {"role": "assistant", "content": "I'm sorry, I cannot help with that."},
        ]
        scores = score_trace(messages, "Check my DPS")
        assert scores["no_give_up"] == 0.0

    def test_focus_detects_player_name(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_my_performance",
                        "arguments": {
                            "encounter_name": "Gruul",
                            "player_name": "Lyroo",
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "Lyroo's DPS on Gruul is 1500."},
        ]
        scores = score_trace(messages, "How is Lyroo doing on Gruul?")
        assert scores["focus"] == 1.0

    def test_focus_fails_when_player_not_mentioned(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_my_performance",
                        "arguments": {"encounter_name": "Gruul"},
                    }
                ],
            },
            {"role": "assistant", "content": "DPS on Gruul is good overall."},
        ]
        scores = score_trace(messages, "How is Lyroo doing on Gruul?")
        assert scores["focus"] == 0.0

    def test_multiple_tool_calls_counted(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_raid_execution",
                        "arguments": {"report_code": "abc123def456gh"},
                    }
                ],
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_activity_report",
                        "arguments": {
                            "report_code": "abc123def456gh",
                            "fight_id": 5,
                            "player_name": "Lyroo",
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "Lyroo's analysis complete."},
        ]
        scores = score_trace(messages, "Analyze Lyroo in abc123def456gh")
        assert scores["depth"] == 2
        assert scores["tool_name_accuracy"] == 1.0

    def test_which_report_ids_not_give_up(self):
        """'which report IDs you have' is helpful, not giving up."""
        messages = [
            {"role": "assistant", "content": (
                "I'd be happy to help analyze your wipe progression. "
                "Just let me know which report IDs you have and I'll "
                "check the data for you."
            )},
        ]
        scores = score_trace(messages, "Show wipe progression on Gruul")
        assert scores["no_give_up"] == 1.0

    def test_unicode_apostrophe_give_up_detected(self):
        """Nemotron uses U+2019 curly apostrophe — must still detect give-up."""
        messages = [
            {"role": "assistant", "content": (
                "I\u2019m sorry, I can\u2019t help with that."
            )},
        ]
        scores = score_trace(messages, "Check my DPS")
        assert scores["no_give_up"] == 0.0

    def test_deep_success_requires_all_metrics(self):
        """Deep success = all binary metrics pass + depth >= 1."""
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "name": "get_spec_leaderboard",
                        "arguments": {"encounter_name": "Gruul"},
                    }
                ],
            },
            {"role": "assistant", "content": "Top specs on Gruul: ..."},
        ]
        scores = score_trace(messages, "Top DPS on Gruul?")
        # All must pass for deep success
        assert scores["tool_name_accuracy"] == 1.0
        assert scores["arg_accuracy"] == 1.0
        assert scores["no_give_up"] == 1.0
        assert scores["depth"] >= 1
