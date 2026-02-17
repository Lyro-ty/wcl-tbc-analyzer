"""Tests for cancelled cast detection."""

from shukketsu.pipeline.event_data import compute_cancelled_casts


class TestComputeCancelledCasts:
    def test_no_cancels(self):
        events = [
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 1000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 2500},
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 3000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 4500},
        ]
        result = compute_cancelled_casts(events)
        assert 1 in result
        data = result[1]
        assert data["total_begins"] == 2
        assert data["total_completions"] == 2
        assert data["cancel_count"] == 0
        assert data["cancel_pct"] == 0.0

    def test_one_cancel(self):
        events = [
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 1000},
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 2000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 3500},
        ]
        result = compute_cancelled_casts(events)
        data = result[1]
        assert data["total_begins"] == 2
        assert data["total_completions"] == 1
        assert data["cancel_count"] == 1
        assert data["cancel_pct"] == 50.0

    def test_multiple_players(self):
        events = [
            # Player 1: 2 begins, 1 complete = 1 cancel
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 1000},
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 2000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 3500},
            # Player 2: 3 begins, 3 complete = 0 cancels
            {"sourceID": 2, "type": "begincast", "abilityGameID": 200, "timestamp": 1000},
            {"sourceID": 2, "type": "cast", "abilityGameID": 200, "timestamp": 2500},
            {"sourceID": 2, "type": "begincast", "abilityGameID": 200, "timestamp": 3000},
            {"sourceID": 2, "type": "cast", "abilityGameID": 200, "timestamp": 4500},
            {"sourceID": 2, "type": "begincast", "abilityGameID": 200, "timestamp": 5000},
            {"sourceID": 2, "type": "cast", "abilityGameID": 200, "timestamp": 6500},
        ]
        result = compute_cancelled_casts(events)
        assert result[1]["cancel_count"] == 1
        assert result[2]["cancel_count"] == 0

    def test_empty_events(self):
        result = compute_cancelled_casts([])
        assert result == {}

    def test_only_instant_casts(self):
        """Events with only 'cast' type (instant casts) — no begins."""
        events = [
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 1000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 2000},
        ]
        result = compute_cancelled_casts(events)
        data = result[1]
        assert data["total_begins"] == 0
        assert data["total_completions"] == 2
        assert data["cancel_count"] == 0

    def test_top_cancelled_spells(self):
        events = [
            # Spell 100: 3 begins, 1 complete = 2 cancels
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 1000},
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 2000},
            {"sourceID": 1, "type": "begincast", "abilityGameID": 100, "timestamp": 3000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 100, "timestamp": 4500},
            # Spell 200: 2 begins, 1 complete = 1 cancel
            {"sourceID": 1, "type": "begincast", "abilityGameID": 200, "timestamp": 5000},
            {"sourceID": 1, "type": "begincast", "abilityGameID": 200, "timestamp": 6000},
            {"sourceID": 1, "type": "cast", "abilityGameID": 200, "timestamp": 7500},
        ]
        result = compute_cancelled_casts(events)
        data = result[1]
        top = data["top_cancelled"]
        assert len(top) == 2
        # Spell 100 should be first (2 cancels > 1 cancel)
        assert top[0][0] == 100
        assert top[0][1] == 2
        assert top[1][0] == 200
        assert top[1][1] == 1
