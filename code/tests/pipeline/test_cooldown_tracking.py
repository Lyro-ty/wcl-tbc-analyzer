"""Tests for cooldown tracking computation."""

from shukketsu.pipeline.constants import CLASSIC_COOLDOWNS
from shukketsu.pipeline.event_data import compute_cooldown_usage


class TestComputeCooldownUsage:
    def test_basic_detection(self):
        """Warrior uses Death Wish once in a 3-minute fight."""
        events = [
            {"timestamp": 5000, "abilityGameID": 12292},  # Death Wish
            {"timestamp": 6000, "abilityGameID": 6572},   # Some other ability
        ]
        result = compute_cooldown_usage(events, "Warrior", fight_duration_ms=180000)

        death_wish = next(r for r in result if r["ability_name"] == "Death Wish")
        assert death_wish["times_used"] == 1
        assert death_wish["max_possible_uses"] == 2  # floor(180/180) + 1
        assert death_wish["efficiency_pct"] == 50.0
        assert death_wish["first_use_ms"] == 5000

    def test_never_used(self):
        """Warrior never uses Death Wish."""
        events = [
            {"timestamp": 1000, "abilityGameID": 6572},  # Not a cooldown
        ]
        result = compute_cooldown_usage(events, "Warrior", fight_duration_ms=180000)

        death_wish = next(r for r in result if r["ability_name"] == "Death Wish")
        assert death_wish["times_used"] == 0
        assert death_wish["efficiency_pct"] == 0.0
        assert death_wish["first_use_ms"] is None

    def test_max_possible_calc(self):
        """5-minute fight, 180s CD = floor(300/180) + 1 = 2 max uses."""
        events = [
            {"timestamp": 1000, "abilityGameID": 12292},
            {"timestamp": 185000, "abilityGameID": 12292},
        ]
        result = compute_cooldown_usage(events, "Warrior", fight_duration_ms=300000)

        death_wish = next(r for r in result if r["ability_name"] == "Death Wish")
        assert death_wish["max_possible_uses"] == 2
        assert death_wish["times_used"] == 2
        assert death_wish["efficiency_pct"] == 100.0

    def test_fight_shorter_than_cd(self):
        """Fight is shorter than the cooldown. max_possible = 1."""
        events = [
            {"timestamp": 1000, "abilityGameID": 12292},
        ]
        result = compute_cooldown_usage(events, "Warrior", fight_duration_ms=30000)

        death_wish = next(r for r in result if r["ability_name"] == "Death Wish")
        assert death_wish["max_possible_uses"] == 1
        assert death_wish["times_used"] == 1
        assert death_wish["efficiency_pct"] == 100.0

    def test_unknown_class(self):
        """Unknown class returns empty list."""
        result = compute_cooldown_usage([], "DeathKnight", fight_duration_ms=180000)
        assert result == []

    def test_all_classes_have_cooldowns(self):
        """All 9 classes in CLASSIC_COOLDOWNS."""
        expected_classes = {
            "Warrior", "Paladin", "Hunter", "Rogue", "Priest",
            "Shaman", "Mage", "Warlock", "Druid",
        }
        assert set(CLASSIC_COOLDOWNS.keys()) == expected_classes

    def test_multiple_cooldowns_same_class(self):
        """Mage has 4 cooldowns — all should appear in result."""
        events = [
            {"timestamp": 1000, "abilityGameID": 12042},  # Arcane Power
            {"timestamp": 2000, "abilityGameID": 12472},  # Icy Veins
        ]
        result = compute_cooldown_usage(events, "Mage", fight_duration_ms=180000)

        names = {r["ability_name"] for r in result}
        assert "Arcane Power" in names
        assert "Evocation" in names
        assert "Combustion" in names
        assert "Icy Veins" in names

        arcane = next(r for r in result if r["ability_name"] == "Arcane Power")
        assert arcane["times_used"] == 1

        icy = next(r for r in result if r["ability_name"] == "Icy Veins")
        assert icy["times_used"] == 1

        # Evocation and Combustion never used
        evo = next(r for r in result if r["ability_name"] == "Evocation")
        assert evo["times_used"] == 0

    def test_efficiency_capped_at_100(self):
        """If somehow more uses than max, cap at 100%."""
        # 10s fight, 180s CD => max_possible = 1
        # But if 3 casts somehow appear
        events = [
            {"timestamp": 1000, "abilityGameID": 12292},
            {"timestamp": 5000, "abilityGameID": 12292},
            {"timestamp": 9000, "abilityGameID": 12292},
        ]
        result = compute_cooldown_usage(events, "Warrior", fight_duration_ms=10000)

        death_wish = next(r for r in result if r["ability_name"] == "Death Wish")
        assert death_wish["efficiency_pct"] == 100.0
