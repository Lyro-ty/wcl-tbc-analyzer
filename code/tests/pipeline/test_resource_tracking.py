"""Tests for resource tracking computation."""

from shukketsu.pipeline.event_data import compute_resource_metrics


class TestComputeResourceMetrics:
    def test_mana_tracking(self):
        events = [
            {"sourceID": 1, "timestamp": 1000,
             "classResources": [{"type": 0, "amount": 8000, "max": 10000}]},
            {"sourceID": 1, "timestamp": 2000,
             "classResources": [{"type": 0, "amount": 6000, "max": 10000}]},
            {"sourceID": 1, "timestamp": 3000,
             "classResources": [{"type": 0, "amount": 4000, "max": 10000}]},
        ]
        result = compute_resource_metrics(events, 5000)
        key = (1, 0)
        assert key in result
        data = result[key]
        assert data["resource_type"] == "mana"
        assert data["min_value"] == 4000
        assert data["max_value"] == 10000
        assert data["avg_value"] == 6000.0

    def test_rage_tracking(self):
        events = [
            {"sourceID": 1, "timestamp": 1000,
             "classResources": [{"type": 1, "amount": 50, "max": 100}]},
            {"sourceID": 1, "timestamp": 2000,
             "classResources": [{"type": 1, "amount": 0, "max": 100}]},
            {"sourceID": 1, "timestamp": 3000,
             "classResources": [{"type": 1, "amount": 80, "max": 100}]},
        ]
        result = compute_resource_metrics(events, 5000)
        key = (1, 1)
        assert key in result
        data = result[key]
        assert data["resource_type"] == "rage"
        assert data["min_value"] == 0

    def test_time_at_zero(self):
        events = [
            {"sourceID": 1, "timestamp": 1000,
             "classResources": [{"type": 0, "amount": 0, "max": 10000}]},
            {"sourceID": 1, "timestamp": 3000,
             "classResources": [{"type": 0, "amount": 5000, "max": 10000}]},
        ]
        result = compute_resource_metrics(events, 10000)
        key = (1, 0)
        data = result[key]
        assert data["time_at_zero_ms"] == 2000
        assert data["time_at_zero_pct"] == 20.0

    def test_empty_events(self):
        result = compute_resource_metrics([], 5000)
        assert result == {}

    def test_unknown_resource_type_ignored(self):
        events = [
            {"sourceID": 1, "timestamp": 1000,
             "classResources": [{"type": 99, "amount": 100, "max": 200}]},
        ]
        result = compute_resource_metrics(events, 5000)
        assert len(result) == 0

    def test_multiple_players(self):
        events = [
            {"sourceID": 1, "timestamp": 1000,
             "classResources": [{"type": 0, "amount": 8000, "max": 10000}]},
            {"sourceID": 2, "timestamp": 1000,
             "classResources": [{"type": 3, "amount": 80, "max": 100}]},
        ]
        result = compute_resource_metrics(events, 5000)
        assert (1, 0) in result
        assert (2, 3) in result
        assert result[(1, 0)]["resource_type"] == "mana"
        assert result[(2, 3)]["resource_type"] == "energy"

    def test_samples_downsampled(self):
        """With many events, samples should be capped."""
        events = [
            {"sourceID": 1, "timestamp": i * 100,
             "classResources": [{"type": 0, "amount": i, "max": 200}]}
            for i in range(200)
        ]
        result = compute_resource_metrics(events, 20000)
        data = result[(1, 0)]
        samples = data["samples"]
        assert len(samples) <= 70  # ~60 + margin from ceiling
