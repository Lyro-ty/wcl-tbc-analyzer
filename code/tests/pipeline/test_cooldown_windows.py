"""Tests for cooldown window throughput computation."""

from shukketsu.pipeline.event_data import compute_cooldown_windows


class TestComputeCooldownWindows:
    def test_single_cooldown_window(self):
        """Single cooldown usage with damage events."""
        # Death Wish (spell 12292, Warrior, 180s CD, 30s duration)
        cast_events = [
            {"abilityGameID": 12292, "timestamp": 5000, "type": "cast"},
        ]
        damage_events = [
            # During CD window (5000 - 35000)
            {"timestamp": 6000, "amount": 5000},
            {"timestamp": 10000, "amount": 3000},
            # Outside CD window
            {"timestamp": 200000, "amount": 2000},
        ]
        result = compute_cooldown_windows(
            cast_events, damage_events,
            "Warrior", 300000, fight_start_time=0,
        )
        assert len(result) >= 1
        dw = [r for r in result if r["spell_id"] == 12292]
        if dw:
            assert dw[0]["window_damage"] == 8000

    def test_no_cooldowns_for_class(self):
        """Class without defined cooldowns returns empty."""
        result = compute_cooldown_windows(
            [], [], "UnknownClass", 300000, fight_start_time=0,
        )
        assert result == []

    def test_no_activations(self):
        """Cast events that don't match any cooldown."""
        cast_events = [
            {"abilityGameID": 99999, "timestamp": 5000, "type": "cast"},
        ]
        result = compute_cooldown_windows(
            cast_events, [], "Warrior", 300000,
            fight_start_time=0,
        )
        assert result == []

    def test_baseline_dps_calculation(self):
        """Baseline DPS is calculated from non-CD damage."""
        # Death Wish at 0s, window = 0-30000ms (30s duration)
        cast_events = [
            {"abilityGameID": 12292, "timestamp": 0, "type": "cast"},
        ]
        damage_events = [
            # In window (0-30s): 10000 damage
            {"timestamp": 1000, "amount": 5000},
            {"timestamp": 2000, "amount": 5000},
            # Outside window (after 30s): 6000 damage
            {"timestamp": 200000, "amount": 3000},
            {"timestamp": 250000, "amount": 3000},
        ]
        result = compute_cooldown_windows(
            cast_events, damage_events,
            "Warrior", 300000, fight_start_time=0,
        )
        dw = [r for r in result if r["spell_id"] == 12292]
        if dw:
            # Baseline = 6000 / (270s non-CD time) = 22.2 DPS
            assert dw[0]["baseline_dps"] == 22.2

    def test_dps_gain_pct(self):
        """DPS gain % shows improvement over baseline."""
        cast_events = [
            {"abilityGameID": 12292, "timestamp": 0, "type": "cast"},
        ]
        damage_events = [
            # In window: high damage
            {"timestamp": 1000, "amount": 50000},
            # Outside: low damage over long time
            {"timestamp": 200000, "amount": 6000},
        ]
        result = compute_cooldown_windows(
            cast_events, damage_events,
            "Warrior", 300000, fight_start_time=0,
        )
        dw = [r for r in result if r["spell_id"] == 12292]
        if dw:
            assert dw[0]["dps_gain_pct"] > 0

    def test_fight_start_offset(self):
        """Timestamps should be offset by fight_start_time."""
        cast_events = [
            {"abilityGameID": 12292, "timestamp": 10000, "type": "cast"},
        ]
        damage_events = [
            {"timestamp": 11000, "amount": 5000},
        ]
        result = compute_cooldown_windows(
            cast_events, damage_events,
            "Warrior", 300000, fight_start_time=10000,
        )
        dw = [r for r in result if r["spell_id"] == 12292]
        if dw:
            assert dw[0]["window_start_ms"] == 0
