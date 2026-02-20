from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState


class TestAnalyzerState:
    def test_has_messages_field(self):
        state = AnalyzerState(messages=[])
        assert "messages" in state

    def test_messages_is_list(self):
        state = AnalyzerState(messages=[])
        assert isinstance(state["messages"], list)


class TestSystemPrompt:
    def test_contains_domain_context(self):
        assert "World of Warcraft" in SYSTEM_PROMPT
        assert "Burning Crusade" in SYSTEM_PROMPT

    def test_contains_class_names(self):
        for cls in ["Warrior", "Rogue", "Mage", "Warlock", "Hunter", "Priest"]:
            assert cls in SYSTEM_PROMPT

    def test_contains_raid_context(self):
        assert "raid" in SYSTEM_PROMPT.lower()
        assert "DPS" in SYSTEM_PROMPT
        assert "parse" in SYSTEM_PROMPT.lower()

    def test_describes_tools(self):
        assert "get_my_performance" in SYSTEM_PROMPT
        assert "get_top_rankings" in SYSTEM_PROMPT
