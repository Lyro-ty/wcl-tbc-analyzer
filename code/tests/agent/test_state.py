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

    def test_has_detected_context_field(self):
        assert "detected_context" in AnalyzerState.__annotations__

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
