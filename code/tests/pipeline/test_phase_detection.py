"""Tests for boss phase detection and per-phase metrics."""

from shukketsu.pipeline.event_data import (
    compute_phase_metrics,
    detect_phases,
)


class TestDetectPhases:
    def test_known_encounter(self):
        phases = detect_phases("Thaddius", 180000)
        assert len(phases) == 3
        assert phases[0]["name"] == "Phase 1 (Stalagg & Feugen)"
        assert phases[0]["start_ms"] == 0
        assert phases[1]["name"] == "Transition"
        assert phases[1]["is_downtime"] is True
        assert phases[2]["name"] == "Phase 2 (Thaddius)"
        assert phases[2]["end_ms"] == 180000

    def test_unknown_encounter(self):
        phases = detect_phases("Patchwerk", 120000)
        assert len(phases) == 1
        assert phases[0]["name"] == "Full Fight"
        assert phases[0]["start_ms"] == 0
        assert phases[0]["end_ms"] == 120000
        assert phases[0]["is_downtime"] is False

    def test_sapphiron_has_downtime(self):
        phases = detect_phases("Sapphiron", 200000)
        assert len(phases) == 2
        ground = phases[0]
        air = phases[1]
        assert ground["is_downtime"] is False
        assert air["is_downtime"] is True
        assert air["name"] == "Air Phase"

    def test_kelthuzad_phases(self):
        phases = detect_phases("Kel'Thuzad", 300000)
        assert len(phases) == 3
        assert phases[0]["name"] == "Phase 1 (Adds)"
        assert phases[2]["end_ms"] == 300000

    def test_zero_duration(self):
        phases = detect_phases("Thaddius", 0)
        assert len(phases) == 3
        for p in phases:
            assert p["start_ms"] == 0
            assert p["end_ms"] == 0


class TestComputePhaseMetrics:
    def test_basic_phase_metrics(self):
        phases = [
            {
                "name": "P1",
                "start_ms": 0,
                "end_ms": 60000,
                "is_downtime": False,
            },
            {
                "name": "P2",
                "start_ms": 60000,
                "end_ms": 120000,
                "is_downtime": False,
            },
        ]
        cast_events = [
            {"timestamp": 1000, "abilityGameID": 100},
            {"timestamp": 5000, "abilityGameID": 100},
            {"timestamp": 70000, "abilityGameID": 100},
        ]
        damage_events = [
            {"timestamp": 2000, "amount": 5000},
            {"timestamp": 6000, "amount": 3000},
            {"timestamp": 75000, "amount": 10000},
        ]
        result = compute_phase_metrics(
            cast_events, damage_events, phases,
            fight_start_time=0, fight_duration_ms=120000,
        )
        assert len(result) == 2
        assert result[0]["phase_name"] == "P1"
        assert result[0]["phase_casts"] == 2
        assert result[0]["phase_dps"] > 0
        assert result[1]["phase_name"] == "P2"
        assert result[1]["phase_casts"] == 1

    def test_empty_events(self):
        phases = [
            {
                "name": "Full",
                "start_ms": 0,
                "end_ms": 60000,
                "is_downtime": False,
            },
        ]
        result = compute_phase_metrics([], [], phases, 0, 60000)
        assert len(result) == 1
        assert result[0]["phase_casts"] == 0
        assert result[0]["phase_dps"] == 0.0

    def test_downtime_phase(self):
        phases = [
            {
                "name": "Active",
                "start_ms": 0,
                "end_ms": 60000,
                "is_downtime": False,
            },
            {
                "name": "Transition",
                "start_ms": 60000,
                "end_ms": 80000,
                "is_downtime": True,
            },
        ]
        result = compute_phase_metrics([], [], phases, 0, 80000)
        assert result[1]["is_downtime"] is True
