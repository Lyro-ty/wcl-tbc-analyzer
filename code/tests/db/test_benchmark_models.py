"""Tests for benchmark ORM models."""

from datetime import UTC, datetime

from shukketsu.db.models import BenchmarkReport, EncounterBenchmark, WatchedGuild


class TestWatchedGuild:
    def test_create(self):
        g = WatchedGuild(
            guild_name="APES",
            wcl_guild_id=12345,
            server_slug="whitemane",
            server_region="US",
            is_active=True,
        )
        assert g.guild_name == "APES"
        assert g.wcl_guild_id == 12345
        assert g.is_active is True

    def test_defaults(self):
        g = WatchedGuild(
            guild_name="Test",
            wcl_guild_id=1,
            server_slug="s",
            server_region="US",
            is_active=True,
        )
        assert g.is_active is True


class TestBenchmarkReport:
    def test_create(self):
        r = BenchmarkReport(
            report_code="abc123",
            source="speed_ranking",
            encounter_id=50649,
            guild_name="APES",
        )
        assert r.report_code == "abc123"
        assert r.source == "speed_ranking"

    def test_watched_guild_source(self):
        r = BenchmarkReport(
            report_code="xyz789",
            source="watched_guild",
            guild_name="Progress",
        )
        assert r.source == "watched_guild"
        assert r.encounter_id is None


class TestEncounterBenchmark:
    def test_create(self):
        b = EncounterBenchmark(
            encounter_id=50649,
            sample_size=10,
            computed_at=datetime.now(UTC),
            benchmarks={"kill": {"avg_duration_ms": 245000}},
        )
        assert b.encounter_id == 50649
        assert b.benchmarks["kill"]["avg_duration_ms"] == 245000
