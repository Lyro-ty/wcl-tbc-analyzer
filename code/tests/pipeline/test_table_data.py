"""Tests for table data pipeline (ability breakdowns, buff uptimes)."""

import pytest

from shukketsu.pipeline.table_data import (
    parse_ability_metrics,
    parse_buff_uptimes,
    parse_table_response,
)


class TestParseTableResponse:
    def test_dict_with_entries(self):
        raw = {"entries": [{"name": "Mortal Strike"}, {"name": "Whirlwind"}]}
        result = parse_table_response(raw)
        assert len(result) == 2
        assert result[0]["name"] == "Mortal Strike"

    def test_json_string(self):
        import json
        raw = json.dumps({"entries": [{"name": "Fireball"}]})
        result = parse_table_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "Fireball"

    def test_list_directly(self):
        raw = [{"name": "Backstab"}, {"name": "Sinister Strike"}]
        result = parse_table_response(raw)
        assert len(result) == 2

    def test_empty_dict(self):
        result = parse_table_response({})
        assert result == []

    def test_none(self):
        result = parse_table_response(None)
        assert result == []

    def test_dict_without_entries(self):
        result = parse_table_response({"data": "something"})
        assert result == []

    def test_data_wrapped_entries(self):
        """WCL v2 table() wraps entries in a 'data' key."""
        raw = {"data": {"entries": [{"name": "Fireball"}, {"name": "Frostbolt"}]}}
        result = parse_table_response(raw)
        assert len(result) == 2
        assert result[0]["name"] == "Fireball"

    def test_data_wrapped_json_string(self):
        """WCL v2 table() may return JSON string with data wrapper."""
        import json
        raw = json.dumps({"data": {"entries": [{"name": "Arcane Blast"}]}})
        result = parse_table_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "Arcane Blast"


class TestParseAbilityMetrics:
    def test_basic_damage_entries(self):
        entries = [
            {"name": "Mortal Strike", "guid": 12294, "total": 50000,
             "hitCount": 20, "critCount": 10, "critPct": 50.0},
            {"name": "Whirlwind", "guid": 1680, "total": 30000,
             "hitCount": 40, "critCount": 8},
            {"name": "Execute", "guid": 5308, "total": 20000,
             "hitCount": 5, "critCount": 3},
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="TestWarr", metric_type="damage",
        )

        assert len(result) == 3
        # Should be sorted by total desc
        assert result[0].ability_name == "Mortal Strike"
        assert result[0].total == 50000
        assert result[0].pct_of_total == 50.0  # 50000/100000 * 100
        assert result[0].crit_pct == 50.0  # from critPct field
        assert result[0].fight_id == 1
        assert result[0].player_name == "TestWarr"
        assert result[0].metric_type == "damage"
        assert result[0].spell_id == 12294

    def test_top_20_limit(self):
        entries = [{"name": f"Spell{i}", "guid": i, "total": 1000 - i} for i in range(30)]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Test", metric_type="damage",
        )
        assert len(result) == 20

    def test_empty_entries(self):
        result = parse_ability_metrics([], fight_id=1, player_name="Test", metric_type="damage")
        assert result == []

    def test_zero_total(self):
        entries = [{"name": "AutoAttack", "guid": 1, "total": 0}]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Test", metric_type="damage",
        )
        assert len(result) == 1
        assert result[0].pct_of_total == 0.0

    def test_crit_pct_calculated_from_counts(self):
        entries = [{"name": "Test", "guid": 1, "total": 1000,
                    "hitCount": 10, "critCount": 4}]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Test", metric_type="damage",
        )
        assert result[0].crit_pct == 40.0

    def test_uses_fallback_for_hit_count(self):
        entries = [{"name": "Test", "guid": 1, "total": 1000, "uses": 15}]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Test", metric_type="damage",
        )
        assert result[0].hit_count == 15


class TestParseBuffUptimes:
    def test_basic_buff_entries(self):
        entries = [
            {"name": "Battle Shout", "guid": 2048, "uptime": 170000},
            {"name": "Flask of Endless Rage", "guid": 53758, "uptime": 180000},
            {"name": "Berserker Rage", "guid": 18499, "uptime": 30000},
        ]
        result = parse_buff_uptimes(
            entries, fight_id=1, player_name="TestWarr",
            metric_type="buff", fight_duration_ms=180000,
        )

        assert len(result) == 3
        # Flask should be first (100% uptime)
        assert result[0].ability_name == "Flask of Endless Rage"
        assert result[0].uptime_pct == 100.0
        # Battle Shout ~94.4%
        assert result[1].ability_name == "Battle Shout"
        assert result[1].uptime_pct == pytest.approx(94.4, abs=0.1)
        # Berserker Rage ~16.7%
        assert result[2].uptime_pct == pytest.approx(16.7, abs=0.1)

    def test_top_30_limit(self):
        entries = [
            {"name": f"Buff{i}", "guid": i, "uptime": 100000 - i * 1000}
            for i in range(40)
        ]
        result = parse_buff_uptimes(
            entries, fight_id=1, player_name="Test",
            metric_type="buff", fight_duration_ms=200000,
        )
        assert len(result) == 30

    def test_empty_entries(self):
        result = parse_buff_uptimes(
            [], fight_id=1, player_name="Test",
            metric_type="buff", fight_duration_ms=180000,
        )
        assert result == []

    def test_uptime_capped_at_100(self):
        entries = [{"name": "Test", "guid": 1, "uptime": 999999}]
        result = parse_buff_uptimes(
            entries, fight_id=1, player_name="Test",
            metric_type="buff", fight_duration_ms=100000,
        )
        assert result[0].uptime_pct == 100.0

    def test_zero_duration_fight(self):
        entries = [{"name": "Test", "guid": 1, "uptime": 1000}]
        result = parse_buff_uptimes(
            entries, fight_id=1, player_name="Test",
            metric_type="buff", fight_duration_ms=0,
        )
        assert result[0].uptime_pct == 0.0
