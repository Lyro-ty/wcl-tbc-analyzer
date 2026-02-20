"""Tests for benchmark config."""

from shukketsu.config import BenchmarkConfig


class TestBenchmarkConfig:
    def test_defaults(self):
        cfg = BenchmarkConfig()
        assert cfg.enabled is True
        assert cfg.refresh_interval_days == 7
        assert cfg.max_reports_per_encounter == 10
        assert cfg.zone_ids == []

    def test_custom_values(self):
        cfg = BenchmarkConfig(
            enabled=False,
            refresh_interval_days=3,
            max_reports_per_encounter=5,
            zone_ids=[1047],
        )
        assert cfg.enabled is False
        assert cfg.refresh_interval_days == 3
