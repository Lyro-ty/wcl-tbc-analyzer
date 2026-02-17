"""Tests for cast metrics (GCD uptime / ABC analysis) computation."""

from shukketsu.pipeline.event_data import (
    GCD_MS,
    compute_cast_metrics,
)


class TestComputeCastMetrics:
    def test_basic_sequence(self):
        events = [
            {"timestamp": 0},
            {"timestamp": 1500},
            {"timestamp": 3000},
            {"timestamp": 4500},
        ]
        result = compute_cast_metrics(events, fight_duration_ms=10000)

        assert result["total_casts"] == 4
        assert result["active_time_ms"] == 4 * GCD_MS  # 6000
        assert result["downtime_ms"] == 10000 - 6000  # 4000
        assert result["gcd_uptime_pct"] == 60.0
        assert result["gap_count"] == 0  # No gaps > 2.5s

    def test_zero_casts(self):
        result = compute_cast_metrics([], fight_duration_ms=10000)

        assert result["total_casts"] == 0
        assert result["casts_per_minute"] == 0.0
        assert result["gcd_uptime_pct"] == 0.0
        assert result["downtime_ms"] == 10000
        assert result["longest_gap_ms"] == 10000

    def test_single_cast(self):
        events = [{"timestamp": 5000}]
        result = compute_cast_metrics(events, fight_duration_ms=10000)

        assert result["total_casts"] == 1
        assert result["active_time_ms"] == GCD_MS
        assert result["gap_count"] == 0  # Only 1 cast, no gaps between casts
        assert result["longest_gap_ms"] == 0  # No gap between casts

    def test_long_gap_detection(self):
        # Cast at 0, then nothing until 5000ms
        events = [
            {"timestamp": 0},
            {"timestamp": 5000},
        ]
        result = compute_cast_metrics(events, fight_duration_ms=6000)

        assert result["total_casts"] == 2
        assert result["longest_gap_ms"] == 5000
        assert result["gap_count"] == 1  # 5000 > GAP_THRESHOLD_MS (2500)

    def test_boundary_gap_threshold(self):
        # Gap of exactly 2499ms — should NOT count
        events = [
            {"timestamp": 0},
            {"timestamp": 2499},
        ]
        result = compute_cast_metrics(events, fight_duration_ms=5000)
        assert result["gap_count"] == 0

        # Gap of exactly 2501ms — SHOULD count
        events2 = [
            {"timestamp": 0},
            {"timestamp": 2501},
        ]
        result2 = compute_cast_metrics(events2, fight_duration_ms=5000)
        assert result2["gap_count"] == 1

    def test_casts_per_minute(self):
        # 60 casts in 60 seconds = 1 CPM
        events = [{"timestamp": i * 1000} for i in range(60)]
        result = compute_cast_metrics(events, fight_duration_ms=60000)

        assert result["total_casts"] == 60
        assert result["casts_per_minute"] == 60.0

    def test_active_time_capped_at_duration(self):
        # More GCDs than fight duration allows
        events = [{"timestamp": i * 100} for i in range(100)]
        result = compute_cast_metrics(events, fight_duration_ms=5000)

        # 100 * 1500 = 150000 > 5000, so capped
        assert result["active_time_ms"] == 5000
        assert result["downtime_ms"] == 0
        assert result["gcd_uptime_pct"] == 100.0

    def test_zero_duration_fight(self):
        events = [{"timestamp": 0}]
        result = compute_cast_metrics(events, fight_duration_ms=0)

        assert result["total_casts"] == 1
        assert result["gcd_uptime_pct"] == 0.0
        assert result["casts_per_minute"] == 0.0

    def test_multiple_significant_gaps(self):
        events = [
            {"timestamp": 0},
            {"timestamp": 5000},   # 5s gap
            {"timestamp": 6000},
            {"timestamp": 10000},  # 4s gap
        ]
        result = compute_cast_metrics(events, fight_duration_ms=12000)

        assert result["gap_count"] == 2
        assert result["longest_gap_ms"] == 5000
        # avg_gap = (5000 + 4000) / 2 = 4500
        assert result["avg_gap_ms"] == 4500.0

    def test_unsorted_events_handled(self):
        # Events arrive out of order — compute_cast_metrics sorts by timestamp
        events = [
            {"timestamp": 3000},
            {"timestamp": 0},
            {"timestamp": 1500},
        ]
        result = compute_cast_metrics(events, fight_duration_ms=5000)

        assert result["total_casts"] == 3
        # Should be sorted: 0, 1500, 3000 — all gaps are 1500ms < threshold
        assert result["gap_count"] == 0
