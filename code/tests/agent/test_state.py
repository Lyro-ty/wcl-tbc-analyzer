from shukketsu.agent.prompts import GRADER_PROMPT, SYSTEM_PROMPT
from shukketsu.agent.state import AnalyzerState


class TestAnalyzerState:
    def test_has_messages_field(self):
        state = AnalyzerState(messages=[])
        assert "messages" in state

    def test_has_query_type(self):
        state = AnalyzerState(messages=[], query_type="my_performance")
        assert state["query_type"] == "my_performance"

    def test_query_type_defaults_none(self):
        state = AnalyzerState(messages=[])
        assert state.get("query_type") is None

    def test_has_encounter_context(self):
        state = AnalyzerState(messages=[], encounter_context={"name": "Gruul"})
        assert state["encounter_context"]["name"] == "Gruul"

    def test_has_character_context(self):
        state = AnalyzerState(messages=[], character_context={"name": "TestRogue"})
        assert state["character_context"]["name"] == "TestRogue"

    def test_has_retry_count(self):
        state = AnalyzerState(messages=[], retry_count=0)
        assert state["retry_count"] == 0

    def test_retry_count_defaults_zero(self):
        state = AnalyzerState(messages=[])
        assert state.get("retry_count", 0) == 0


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


class TestGraderPrompt:
    def test_exists_and_nonempty(self):
        assert len(GRADER_PROMPT) > 0

    def test_mentions_relevance(self):
        assert "relevant" in GRADER_PROMPT.lower()
