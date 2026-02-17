"""Tests for per-spec rotation validation."""

from shukketsu.pipeline.rotation_rules import (
    SPEC_ROTATIONS,
    evaluate_rotation,
)


class TestSpecRotations:
    def test_fury_rules_defined(self):
        assert "Fury" in SPEC_ROTATIONS
        assert len(SPEC_ROTATIONS["Fury"]) == 4

    def test_combat_rules_defined(self):
        assert "Combat" in SPEC_ROTATIONS
        assert len(SPEC_ROTATIONS["Combat"]) == 4

    def test_arcane_rules_defined(self):
        assert "Arcane" in SPEC_ROTATIONS
        assert len(SPEC_ROTATIONS["Arcane"]) == 4

    def test_unknown_spec_returns_empty(self):
        report = evaluate_rotation([], {}, "Survival", 120000)
        assert report.rules_checked == 0
        assert report.score_pct == 0.0


class TestEvaluateRotation:
    def test_perfect_fury_rotation(self):
        """Fury warrior with perfect CD usage and cast counts."""
        fight_ms = 180000  # 3 minutes
        # BT: 6s CD -> max 31, used 25 (80%)
        # WW: 10s CD -> max 19, used 12 (63%)
        # HS: 30+ casts in 3 min = 10/min
        cast_events = (
            [{"abilityGameID": 23881, "timestamp": i * 6000}
             for i in range(25)]
            + [{"abilityGameID": 25231, "timestamp": i * 10000}
               for i in range(12)]
            + [{"abilityGameID": 29707, "timestamp": i * 5500}
               for i in range(33)]
        )
        # Rampage buff with 85% uptime
        buff_uptimes = {29801: 85.0}

        report = evaluate_rotation(
            cast_events, buff_uptimes, "Fury", fight_ms,
        )
        assert report.rules_checked == 4
        assert report.rules_passed >= 3  # Most should pass
        assert report.score_pct >= 75.0

    def test_poor_fury_rotation(self):
        """Fury warrior barely casting."""
        fight_ms = 180000
        cast_events = [
            {"abilityGameID": 23881, "timestamp": 0},
            {"abilityGameID": 23881, "timestamp": 60000},
        ]
        report = evaluate_rotation(cast_events, {}, "Fury", fight_ms)
        assert report.rules_checked == 4
        assert report.rules_passed < 4
        assert len(report.violations) > 0

    def test_combat_rogue_with_snd_uptime(self):
        """Combat rogue with good SnD uptime."""
        fight_ms = 120000  # 2 minutes
        cast_events = (
            [{"abilityGameID": 26862, "timestamp": i * 3000}
             for i in range(40)]
            + [{"abilityGameID": 13877, "timestamp": 0}]
            + [{"abilityGameID": 13750, "timestamp": 0}]
        )
        # SnD 95% uptime
        buff_uptimes = {6774: 95.0}

        report = evaluate_rotation(
            cast_events, buff_uptimes, "Combat", fight_ms,
        )
        assert report.rules_checked == 4
        assert report.score_pct >= 50.0

    def test_empty_events(self):
        report = evaluate_rotation([], {}, "Fury", 120000)
        assert report.rules_checked == 4
        assert report.rules_passed == 0
        assert report.score_pct == 0.0
        assert len(report.violations) == 4

    def test_zero_duration_fight(self):
        report = evaluate_rotation([], {}, "Arcane", 0)
        assert report.rules_checked == 4
        assert report.score_pct == 0.0

    def test_violations_contain_details(self):
        report = evaluate_rotation([], {}, "Fury", 120000)
        for v in report.violations:
            assert "rule" in v
            assert "description" in v
            assert "actual" in v
            assert "expected" in v
            assert "detail" in v
