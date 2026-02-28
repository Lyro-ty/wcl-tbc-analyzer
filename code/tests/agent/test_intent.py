from shukketsu.agent.intent import classify_intent


class TestClassifyIntent:
    def test_report_analysis(self):
        result = classify_intent("Analyze report Fn2ACKZtyzc1QLJP")
        assert result.intent == "report_analysis"
        assert result.report_code == "Fn2ACKZtyzc1QLJP"

    def test_player_analysis(self):
        result = classify_intent(
            "Can you analyze report Fn2ACKZtyzc1QLJP and tell me "
            "what Lyroo could have done better?"
        )
        assert result.intent == "player_analysis"
        assert result.report_code == "Fn2ACKZtyzc1QLJP"
        assert "Lyroo" in result.player_names

    def test_compare_to_top(self):
        result = classify_intent(
            "How does our raid compare to top guilds on Magtheridon?"
        )
        assert result.intent == "compare_to_top"

    def test_benchmarks_encounter(self):
        result = classify_intent(
            "Show me encounter benchmarks for Gruul the Dragonkiller"
        )
        assert result.intent == "benchmarks"
        assert result.encounter_name == "Gruul the Dragonkiller"

    def test_benchmarks_spec(self):
        result = classify_intent(
            "What are the benchmark targets for Destruction Warlock on Gruul?"
        )
        assert result.intent == "benchmarks"
        assert result.class_name == "Warlock"
        assert result.spec_name == "Destruction"

    def test_progression(self):
        result = classify_intent("Show me Lyroo's progression over time")
        assert result.intent == "progression"
        assert "Lyroo" in result.player_names

    def test_specific_rotation(self):
        result = classify_intent(
            "Pull a rotation score for Lyroo on report Fn2ACKZtyzc1QLJP"
        )
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_rotation_score"
        assert result.report_code == "Fn2ACKZtyzc1QLJP"

    def test_specific_deaths(self):
        result = classify_intent("Show me death analysis for the Gruul fight")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_death_analysis"

    def test_specific_cooldowns(self):
        result = classify_intent("How is Lyroo's cooldown usage?")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_cooldown_efficiency"

    def test_specific_consumables(self):
        result = classify_intent("Check consumables for Magtheridon")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_consumable_check"

    def test_specific_buffs(self):
        result = classify_intent("Show buff uptimes for Lyroo")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_buff_analysis"

    def test_specific_gear(self):
        result = classify_intent("Check Lyroo's enchants and gems")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_enchant_gem_check"

    def test_specific_resource(self):
        result = classify_intent("How is Lyroo's mana usage?")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_resource_usage"

    def test_specific_dots(self):
        result = classify_intent("Check dot management for Lyroo")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_dot_management"

    def test_specific_cancelled_casts(self):
        result = classify_intent("Show cancelled casts for Lyroo")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_cancelled_casts"

    def test_specific_ability(self):
        result = classify_intent("Show ability breakdown for Lyroo")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_ability_breakdown"

    def test_specific_overheal(self):
        result = classify_intent("How much is Lyroo overhealing?")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_overheal_analysis"

    def test_specific_activity(self):
        result = classify_intent("Show me GCD uptime for Lyroo")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_activity_report"

    def test_specific_phase(self):
        result = classify_intent("Show phase breakdown for Prince fight")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_phase_analysis"

    def test_leaderboard(self):
        result = classify_intent("What specs top DPS on Gruul?")
        assert result.intent == "leaderboard"

    def test_unknown(self):
        result = classify_intent("Hello, how are you?")
        assert result.intent is None

    def test_compare_two_raids(self):
        result = classify_intent(
            "Compare report ABC123def456ghij to report XYZ789abc012defg"
        )
        assert result.intent == "compare_to_top"

    def test_wipe_progression(self):
        result = classify_intent(
            "Show wipe progression for Magtheridon in Fn2ACKZtyzc1QLJP"
        )
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_wipe_progression"

    def test_search_fights(self):
        result = classify_intent("Search for all Gruul fights")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "search_fights"

    def test_regressions(self):
        result = classify_intent("Check for performance regressions")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_regressions"


class TestExtractSpecClass:
    """Test class/spec extraction from natural language."""

    def test_destruction_warlock(self):
        result = classify_intent("Benchmark targets for Destruction Warlock")
        assert result.class_name == "Warlock"
        assert result.spec_name == "Destruction"

    def test_arms_warrior(self):
        result = classify_intent("How does Arms Warrior do on Gruul?")
        assert result.class_name == "Warrior"
        assert result.spec_name == "Arms"

    def test_holy_priest(self):
        result = classify_intent("Show benchmarks for Holy Priest")
        assert result.class_name == "Priest"
        assert result.spec_name == "Holy"

    def test_beast_mastery_hunter(self):
        result = classify_intent("Beast Mastery Hunter benchmarks")
        assert result.class_name == "Hunter"
        assert result.spec_name == "BeastMastery"

    def test_no_spec(self):
        result = classify_intent("How does Warlock do on Gruul?")
        assert result.class_name == "Warlock"
        assert result.spec_name is None


class TestEdgeCases:
    """Test edge cases and improvements over the plan."""

    def test_report_code_in_url(self):
        result = classify_intent(
            "Analyze https://classic.warcraftlogs.com/reports/Fn2ACKZtyzc1QLJP"
        )
        assert result.report_code == "Fn2ACKZtyzc1QLJP"
        assert result.intent == "report_analysis"

    def test_encounter_name_word_boundary(self):
        """Encounter names should match on word boundaries, not substrings."""
        result = classify_intent("What is the warranty for this product?")
        # "Aran" should NOT match inside "warranty"
        assert result.encounter_name is None

    def test_multiple_player_names(self):
        result = classify_intent(
            "Compare Lyroo and Flasheal on Fn2ACKZtyzc1QLJP"
        )
        assert "Lyroo" in result.player_names
        assert "Flasheal" in result.player_names

    def test_player_name_not_boss_name(self):
        result = classify_intent("How did players do on Gruul?")
        assert "Gruul" not in result.player_names

    def test_player_analysis_needs_report_and_player(self):
        """player_analysis requires both a report code and player name."""
        result = classify_intent("What could Lyroo do better?")
        # No report code → should NOT be player_analysis
        assert result.intent != "player_analysis"

    def test_specific_tool_takes_priority_over_report(self):
        """Even with report code, specific tool keywords win."""
        result = classify_intent(
            "Show rotation score for Fn2ACKZtyzc1QLJP"
        )
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_rotation_score"

    def test_gear_changes(self):
        result = classify_intent("Show gear changes between raids")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_gear_changes"

    def test_deaths_and_mechanics(self):
        """'deaths' keyword should map to get_death_analysis."""
        result = classify_intent("Show deaths on Gruul")
        assert result.intent == "specific_tool"
        assert result.specific_tool == "get_death_analysis"
