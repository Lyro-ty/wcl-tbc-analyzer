"""Tests for benchmark-driven rotation scoring in event_tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.agent.tools.event_tools import _fetch_benchmark_rules, get_rotation_score

# -- Sample benchmark data ---------------------------------------------------

def _benchmark_json(
    *,
    spec_key="Fury Warrior",
    gcd_uptime=92.0,
    cpm=34.0,
    median_dps=2800.0,
    median_hps=None,
    cd_efficiency=88.0,
    abilities=None,
):
    """Build a minimal benchmark JSON dict matching encounter_benchmarks schema."""
    if abilities is None:
        abilities = [
            {"ability_name": "Bloodthirst", "avg_damage_pct": 35.0},
            {"ability_name": "Whirlwind", "avg_damage_pct": 22.0},
            {"ability_name": "Heroic Strike", "avg_damage_pct": 15.0},
            {"ability_name": "Execute", "avg_damage_pct": 10.0},
            {"ability_name": "Deep Wounds", "avg_damage_pct": 8.0},
            {"ability_name": "Hamstring", "avg_damage_pct": 2.0},
        ]
    dps_data = {"median_dps": median_dps}
    if median_hps is not None:
        dps_data["median_hps"] = median_hps

    return {
        "by_spec": {
            spec_key: {
                "gcd": {"avg_gcd_uptime": gcd_uptime, "avg_cpm": cpm},
                "dps": dps_data,
                "abilities": abilities,
                "cooldowns": [
                    {"ability_name": "Death Wish", "avg_efficiency": cd_efficiency},
                    {"ability_name": "Recklessness", "avg_efficiency": 70.0},
                ],
            },
        },
    }


def _make_benchmark_mock(benchmarks):
    """Create a mock result for GET_BENCHMARK_BY_ENCOUNTER_ID."""
    row = MagicMock(benchmarks=benchmarks)
    result = MagicMock()
    result.fetchone.return_value = row
    return result


def _no_benchmark_mock():
    """Create a mock result returning None (no benchmark data)."""
    result = MagicMock()
    result.fetchone.return_value = None
    return result


# -- Helper: _fetch_benchmark_rules ------------------------------------------

class TestFetchBenchmarkRules:
    async def test_returns_rules_when_benchmark_exists(self):
        """Returns (SpecRules, median_dps) when benchmark has matching spec."""
        benchmarks = _benchmark_json(
            spec_key="Fury Warrior", gcd_uptime=92.0, cpm=34.0,
            median_dps=2800.0, cd_efficiency=88.0,
        )
        bench_mock = _make_benchmark_mock(benchmarks)

        session = AsyncMock()
        session.execute.return_value = bench_mock

        result = await _fetch_benchmark_rules(
            session, 50651, "Warrior", "Fury",
        )

        assert result is not None
        rules, median_dps = result
        assert rules.gcd_target == 92.0
        assert rules.cpm_target == 34.0
        assert rules.role == "melee_dps"
        assert median_dps == 2800.0
        # Top 5 abilities by avg_damage_pct
        assert "Bloodthirst" in rules.key_abilities
        assert "Whirlwind" in rules.key_abilities
        assert len(rules.key_abilities) <= 5
        # Hamstring (2%) should be excluded (6th ability)
        assert "Hamstring" not in rules.key_abilities
        # CD efficiency = avg of 88.0 and 70.0 = 79.0
        assert rules.cd_efficiency_target == 79.0

    async def test_returns_none_when_no_benchmark(self):
        """Returns None when no benchmark row exists."""
        session = AsyncMock()
        session.execute.return_value = _no_benchmark_mock()

        result = await _fetch_benchmark_rules(
            session, 99999, "Warrior", "Fury",
        )
        assert result is None

    async def test_returns_none_when_spec_missing(self):
        """Returns None when benchmark exists but spec not in by_spec."""
        benchmarks = _benchmark_json(spec_key="Fury Warrior")
        bench_mock = _make_benchmark_mock(benchmarks)

        session = AsyncMock()
        session.execute.return_value = bench_mock

        # Request a spec that doesn't exist in the benchmark
        result = await _fetch_benchmark_rules(
            session, 50651, "Mage", "Frost",
        )
        assert result is None

    async def test_handles_json_string(self):
        """Handles benchmarks column stored as JSON string (not dict)."""
        benchmarks = _benchmark_json(
            spec_key="Fury Warrior", median_dps=3000.0,
        )
        # Store as JSON string to simulate WCL JSON scalar behavior
        bench_mock = _make_benchmark_mock(json.dumps(benchmarks))

        session = AsyncMock()
        session.execute.return_value = bench_mock

        result = await _fetch_benchmark_rules(
            session, 50651, "Warrior", "Fury",
        )
        assert result is not None
        rules, median_dps = result
        assert median_dps == 3000.0
        assert rules.gcd_target > 0

    async def test_healer_uses_median_hps(self):
        """For healers, benchmark_dps should be median_hps (not median_dps)."""
        benchmarks = _benchmark_json(
            spec_key="Holy Paladin", gcd_uptime=55.0, cpm=18.0,
            median_dps=50.0, median_hps=1800.0, cd_efficiency=70.0,
            abilities=[
                {"ability_name": "Flash of Light", "avg_damage_pct": 60.0},
                {"ability_name": "Holy Light", "avg_damage_pct": 35.0},
            ],
        )
        bench_mock = _make_benchmark_mock(benchmarks)

        session = AsyncMock()
        session.execute.return_value = bench_mock

        result = await _fetch_benchmark_rules(
            session, 50651, "Paladin", "Holy",
        )
        assert result is not None
        rules, median_hps = result
        assert rules.role == "healer"
        assert median_hps == 1800.0  # Should prefer median_hps


# -- Integration: get_rotation_score with benchmark --------------------------

def _benchmark_rotation_mocks(
    *,
    player_class="Warrior",
    player_spec="Fury",
    encounter_name="Gruul the Dragonkiller",
    encounter_id=50651,
    player_dps=2500.0,
    gcd_uptime_pct=90.0,
    casts_per_minute=32.0,
    benchmarks=None,
    cd_rows=None,
    ability_rows=None,
):
    """Build mock execute results for get_rotation_score with benchmark data.

    Returns a mock_session with side_effect for:
      1. PLAYER_FIGHT_INFO
      2. GET_BENCHMARK_BY_ENCOUNTER_ID
      3. FIGHT_CAST_METRICS
      4. FIGHT_COOLDOWNS
      5. ABILITY_BREAKDOWN
    """
    # 1. PLAYER_FIGHT_INFO
    info_row = MagicMock(
        player_class=player_class,
        player_spec=player_spec,
        dps=player_dps,
        total_damage=int(player_dps * 180),
        fight_duration_ms=180000,
        encounter_id=encounter_id,
        encounter_name=encounter_name,
    )
    info_result = MagicMock()
    info_result.fetchone.return_value = info_row

    # 2. GET_BENCHMARK_BY_ENCOUNTER_ID
    if benchmarks is not None:
        bench_result = _make_benchmark_mock(benchmarks)
    else:
        bench_result = _no_benchmark_mock()

    # 3. FIGHT_CAST_METRICS
    cm_row = MagicMock(
        player_name="TestPlayer",
        total_casts=150,
        casts_per_minute=casts_per_minute,
        gcd_uptime_pct=gcd_uptime_pct,
        active_time_ms=162000,
        downtime_ms=18000,
        longest_gap_ms=3000,
        longest_gap_at_ms=60000,
        avg_gap_ms=500.0,
        gap_count=10,
    )
    cm_result = MagicMock()
    cm_result.fetchone.return_value = cm_row

    # 4. FIGHT_COOLDOWNS
    if cd_rows is None:
        cd_rows = [
            MagicMock(
                player_name="TestPlayer",
                ability_name="Death Wish",
                spell_id=12292,
                cooldown_sec=180,
                times_used=2,
                max_possible_uses=2,
                first_use_ms=5000,
                last_use_ms=185000,
                efficiency_pct=100.0,
            ),
        ]
    cd_result = MagicMock()
    cd_result.fetchall.return_value = cd_rows

    # 5. ABILITY_BREAKDOWN
    if ability_rows is None:
        ability_rows = [
            MagicMock(
                player_name="TestPlayer", metric_type="damage",
                ability_name="Bloodthirst", spell_id=23881,
                total=200000, hit_count=50, crit_count=25,
                crit_pct=50.0, pct_of_total=44.0,
            ),
            MagicMock(
                player_name="TestPlayer", metric_type="damage",
                ability_name="Whirlwind", spell_id=1680,
                total=120000, hit_count=40, crit_count=15,
                crit_pct=37.5, pct_of_total=26.0,
            ),
        ]
    ability_result = MagicMock()
    ability_result.fetchall.return_value = ability_rows

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [
        info_result, bench_result, cm_result, cd_result, ability_result,
    ]
    return mock_session


class TestBenchmarkDrivenRotationScore:
    async def test_uses_benchmark_when_available(self):
        """Rotation score uses benchmark rules and shows source=benchmark."""
        benchmarks = _benchmark_json(
            spec_key="Fury Warrior", gcd_uptime=88.0, cpm=30.0,
            median_dps=2800.0, cd_efficiency=85.0,
        )
        mock_session = _benchmark_rotation_mocks(
            player_class="Warrior", player_spec="Fury",
            encounter_name="Gruul the Dragonkiller",
            gcd_uptime_pct=90.0, casts_per_minute=32.0,
            player_dps=2500.0,
            benchmarks=benchmarks,
        )

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_rotation_score.ainvoke(
                {"report_code": "abc123", "fight_id": 1,
                 "player_name": "TestPlayer"}
            )

        assert "benchmark" in result.lower()
        assert "Top player median DPS: 2,800.0" in result
        assert "Your DPS: 2,500.0" in result

    async def test_falls_back_to_hardcoded_when_no_benchmark(self):
        """Uses hardcoded SPEC_ROTATION_RULES when no benchmark exists."""
        mock_session = _benchmark_rotation_mocks(
            player_class="Warrior", player_spec="Fury",
            encounter_name="Gruul the Dragonkiller",
            gcd_uptime_pct=90.0, casts_per_minute=32.0,
            benchmarks=None,  # No benchmark data
        )

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_rotation_score.ainvoke(
                {"report_code": "abc123", "fight_id": 1,
                 "player_name": "TestPlayer"}
            )

        assert "Source: default" in result
        # Should NOT contain benchmark DPS comparison
        assert "Top player median DPS" not in result
        # Should reference hardcoded Fury targets: GCD 90%, CPM 32
        assert "GCD target: 90" in result
        assert "CPM target: 32" in result

    async def test_benchmark_skips_encounter_context(self):
        """Benchmark source skips ENCOUNTER_CONTEXTS modifier."""
        # Shade of Aran has gcd_modifier=0.85 in ENCOUNTER_CONTEXTS
        # With benchmark source, modifier should NOT be applied
        benchmarks = _benchmark_json(
            spec_key="Fire Mage", gcd_uptime=80.0, cpm=20.0,
            median_dps=2000.0, cd_efficiency=80.0,
            abilities=[
                {"ability_name": "Fireball", "avg_damage_pct": 60.0},
                {"ability_name": "Scorch", "avg_damage_pct": 15.0},
                {"ability_name": "Fire Blast", "avg_damage_pct": 10.0},
            ],
        )
        mock_session = _benchmark_rotation_mocks(
            player_class="Mage", player_spec="Fire",
            encounter_name="Shade of Aran",
            encounter_id=50658,
            gcd_uptime_pct=82.0, casts_per_minute=21.0,
            player_dps=1800.0,
            benchmarks=benchmarks,
            ability_rows=[
                MagicMock(
                    player_name="TestPlayer", metric_type="damage",
                    ability_name="Fireball", spell_id=133,
                    total=200000, hit_count=50, crit_count=25,
                    crit_pct=50.0, pct_of_total=60.0,
                ),
                MagicMock(
                    player_name="TestPlayer", metric_type="damage",
                    ability_name="Scorch", spell_id=2948,
                    total=50000, hit_count=20, crit_count=10,
                    crit_pct=50.0, pct_of_total=15.0,
                ),
                MagicMock(
                    player_name="TestPlayer", metric_type="damage",
                    ability_name="Fire Blast", spell_id=2136,
                    total=30000, hit_count=10, crit_count=5,
                    crit_pct=50.0, pct_of_total=9.0,
                ),
            ],
        )

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_rotation_score.ainvoke(
                {"report_code": "abc123", "fight_id": 1,
                 "player_name": "TestPlayer"}
            )

        # Benchmark target is 80.0%, player has 82.0% -> should pass
        # If encounter modifier was applied: 80*0.85=68% (would also pass)
        # Key check: no "Encounter context" line in output
        assert "Encounter context" not in result
        assert "modifier" not in result
        assert "benchmark" in result.lower()
        # GCD should pass (82% >= 80% benchmark target) — no GCD violation
        assert "Violations" not in result

    async def test_benchmark_with_missing_spec_falls_back(self):
        """Falls back to hardcoded when benchmark exists but spec missing."""
        # Benchmark has Arms Warrior but player is Fury Warrior
        benchmarks = _benchmark_json(spec_key="Arms Warrior")
        mock_session = _benchmark_rotation_mocks(
            player_class="Warrior", player_spec="Fury",
            encounter_name="Gruul the Dragonkiller",
            gcd_uptime_pct=90.0, casts_per_minute=32.0,
            benchmarks=benchmarks,
        )

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_rotation_score.ainvoke(
                {"report_code": "abc123", "fight_id": 1,
                 "player_name": "TestPlayer"}
            )

        # Should fall back to hardcoded since Fury Warrior not in benchmark
        assert "Source: default" in result
        assert "GCD target: 90" in result  # Hardcoded Fury target

    async def test_benchmark_key_abilities_top_5(self):
        """Benchmark key abilities are limited to top 5 by avg_damage_pct."""
        abilities = [
            {"ability_name": f"Spell{i}", "avg_damage_pct": 30.0 - i * 5}
            for i in range(7)
        ]
        benchmarks = _benchmark_json(
            spec_key="Fury Warrior", abilities=abilities,
        )

        session = AsyncMock()
        session.execute.return_value = _make_benchmark_mock(benchmarks)

        result = await _fetch_benchmark_rules(
            session, 50651, "Warrior", "Fury",
        )
        assert result is not None
        rules, _ = result
        assert len(rules.key_abilities) == 5
        assert rules.key_abilities[0] == "Spell0"  # Highest pct
        assert "Spell5" not in rules.key_abilities
        assert "Spell6" not in rules.key_abilities
