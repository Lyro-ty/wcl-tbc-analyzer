"""Tests for DoT refresh detection."""

from shukketsu.pipeline.event_data import compute_dot_refreshes


class TestComputeDotRefreshes:
    def test_no_dots_for_class(self):
        """Warrior has no DoTs defined."""
        events = [
            {"abilityGameID": 12294, "timestamp": 1000},
        ]
        result = compute_dot_refreshes(events, "Warrior")
        assert result == []

    def test_no_refresh(self):
        """Single application, no refresh."""
        events = [
            {"abilityGameID": 27216, "timestamp": 1000},  # Corruption
        ]
        result = compute_dot_refreshes(events, "Warlock")
        assert len(result) == 1
        assert result[0]["ability_name"] == "Corruption"
        assert result[0]["total_refreshes"] == 0
        assert result[0]["early_refreshes"] == 0

    def test_safe_refresh(self):
        """Refresh within pandemic window (last 30%)."""
        # Corruption: 18s duration, pandemic at 12.6s+
        events = [
            {"abilityGameID": 27216, "timestamp": 0},
            # Refresh at 14s -- within pandemic window (12.6s+)
            {"abilityGameID": 27216, "timestamp": 14000},
        ]
        result = compute_dot_refreshes(events, "Warlock")
        assert len(result) == 1
        assert result[0]["total_refreshes"] == 1
        assert result[0]["early_refreshes"] == 0

    def test_early_refresh(self):
        """Refresh before pandemic window = early."""
        # Corruption: 18s duration, pandemic starts at 12.6s
        events = [
            {"abilityGameID": 27216, "timestamp": 0},
            # Refresh at 8s -- 10s remaining, before pandemic window
            {"abilityGameID": 27216, "timestamp": 8000},
        ]
        result = compute_dot_refreshes(events, "Warlock")
        assert len(result) == 1
        assert result[0]["total_refreshes"] == 1
        assert result[0]["early_refreshes"] == 1
        assert result[0]["early_refresh_pct"] == 100.0
        assert result[0]["avg_remaining_ms"] == 10000.0
        # 10000ms / 3000ms tick = 3 clipped ticks
        assert result[0]["clipped_ticks_est"] == 3

    def test_multiple_dots(self):
        """Multiple DoT spells tracked independently."""
        events = [
            {"abilityGameID": 27216, "timestamp": 0},      # Corruption
            {"abilityGameID": 27215, "timestamp": 500},     # Immolate
            # Early refresh on Corruption at 5s
            {"abilityGameID": 27216, "timestamp": 5000},
            # Safe refresh on Immolate at 13s (pandemic at 10.5s)
            {"abilityGameID": 27215, "timestamp": 13000},
        ]
        result = compute_dot_refreshes(events, "Warlock")
        assert len(result) == 2
        corr = next(r for r in result if r["ability_name"] == "Corruption")
        immo = next(r for r in result if r["ability_name"] == "Immolate")
        assert corr["early_refreshes"] == 1
        assert immo["early_refreshes"] == 0

    def test_priest_shadow_dots(self):
        """Shadow Priest DoTs tracked correctly."""
        events = [
            {"abilityGameID": 25368, "timestamp": 0},      # SW:Pain
            {"abilityGameID": 34917, "timestamp": 1000},    # VT
            # Early refresh SW:Pain at 6s (12s remaining)
            {"abilityGameID": 25368, "timestamp": 6000},
        ]
        result = compute_dot_refreshes(events, "Priest")
        swp = next(
            r for r in result if r["ability_name"] == "Shadow Word: Pain"
        )
        assert swp["early_refreshes"] == 1

    def test_empty_events(self):
        result = compute_dot_refreshes([], "Warlock")
        assert result == []
