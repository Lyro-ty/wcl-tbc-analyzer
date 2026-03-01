from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState


class TestAnalyzerState:
    def test_has_messages_field(self):
        state = AnalyzerState(messages=[])
        assert "messages" in state

    def test_messages_is_list(self):
        state = AnalyzerState(messages=[])
        assert isinstance(state["messages"], list)

    def test_has_intent_field(self):
        assert "intent" in AnalyzerState.__annotations__

    def test_has_tool_error_count_field(self):
        assert "tool_error_count" in AnalyzerState.__annotations__


class TestSystemPrompt:
    def test_contains_domain_context(self):
        assert "TBC" in SYSTEM_PROMPT
        assert "Karazhan" in SYSTEM_PROMPT

    def test_contains_class_names(self):
        for cls in ["Warrior", "Rogue", "Mage", "Warlock", "Hunter", "Priest"]:
            assert cls in SYSTEM_PROMPT

    def test_contains_raid_context(self):
        assert "raid" in SYSTEM_PROMPT.lower()
        assert "DPS" in SYSTEM_PROMPT

    def test_describes_analysis_focus(self):
        assert "ANALYZE" in SYSTEM_PROMPT
        assert "Overview" in SYSTEM_PROMPT

    def test_contains_few_shot_examples(self):
        assert "EXAMPLE" in SYSTEM_PROMPT or "Example" in SYSTEM_PROMPT

    def test_contains_error_recovery_instructions(self):
        assert "error" in SYSTEM_PROMPT.lower()
        assert "retry" in SYSTEM_PROMPT.lower() or "fix" in SYSTEM_PROMPT.lower()

    def test_contains_player_focus_rule(self):
        assert "player" in SYSTEM_PROMPT.lower()

    def test_prompt_under_2000_tokens(self):
        # Rough estimate: 1 token ~ 4 chars
        assert len(SYSTEM_PROMPT) < 8000

    def test_contains_conversation_context_rule(self):
        assert "conversation" in SYSTEM_PROMPT.lower()

    def test_contains_tool_call_examples(self):
        """Prompt should show correct tool call patterns."""
        assert "report_code" in SYSTEM_PROMPT
        assert "fight_id" in SYSTEM_PROMPT
        assert "player_name" in SYSTEM_PROMPT

    def test_player_name_in_response_rule(self):
        """Prompt must instruct LLM to always name the player in responses."""
        lower = SYSTEM_PROMPT.lower()
        assert "name" in lower and "response" in lower

    def test_personal_records_example(self):
        """Prompt must have example for personal records (bests_only)."""
        assert "bests_only" in SYSTEM_PROMPT

    def test_progression_example(self):
        """Prompt must have example for progression queries."""
        assert "get_progression" in SYSTEM_PROMPT
