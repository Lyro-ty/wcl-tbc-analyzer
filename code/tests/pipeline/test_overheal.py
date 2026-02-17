"""Tests for overhealing analysis via table_data parsing."""

from shukketsu.pipeline.table_data import parse_ability_metrics


class TestOverhealParsing:
    def test_healing_entry_with_overheal(self):
        entries = [
            {
                "name": "Chain Heal",
                "guid": 25423,
                "total": 50000,
                "overheal": 15000,
                "hitCount": 30,
                "critCount": 10,
            },
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Healer",
            metric_type="healing",
        )
        assert len(result) == 1
        assert result[0].ability_name == "Chain Heal"
        assert result[0].overheal_total == 15000

    def test_healing_entry_without_overheal(self):
        entries = [
            {
                "name": "Heal",
                "guid": 6063,
                "total": 30000,
                "hitCount": 20,
                "critCount": 5,
            },
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Healer",
            metric_type="healing",
        )
        assert len(result) == 1
        assert result[0].overheal_total is None

    def test_damage_entry_no_overheal(self):
        entries = [
            {
                "name": "Mortal Strike",
                "guid": 12294,
                "total": 80000,
                "hitCount": 40,
                "critCount": 15,
            },
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Warrior",
            metric_type="damage",
        )
        assert len(result) == 1
        assert result[0].overheal_total is None

    def test_total_overheal_alias(self):
        """WCL sometimes uses totalOverheal instead of overheal."""
        entries = [
            {
                "name": "Holy Light",
                "guid": 27137,
                "total": 60000,
                "totalOverheal": 20000,
                "hitCount": 25,
                "critCount": 8,
            },
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Paladin",
            metric_type="healing",
        )
        assert len(result) == 1
        assert result[0].overheal_total == 20000

    def test_multiple_healing_abilities(self):
        entries = [
            {
                "name": "Chain Heal",
                "guid": 25423,
                "total": 50000,
                "overheal": 15000,
                "hitCount": 30,
                "critCount": 10,
            },
            {
                "name": "Healing Wave",
                "guid": 25357,
                "total": 30000,
                "overheal": 5000,
                "hitCount": 15,
                "critCount": 3,
            },
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Shaman",
            metric_type="healing",
        )
        assert len(result) == 2
        # Sorted by total descending
        assert result[0].ability_name == "Chain Heal"
        assert result[0].overheal_total == 15000
        assert result[1].ability_name == "Healing Wave"
        assert result[1].overheal_total == 5000

    def test_overheal_zero_treated_as_none(self):
        entries = [
            {
                "name": "Renew",
                "guid": 25222,
                "total": 20000,
                "overheal": 0,
                "hitCount": 10,
                "critCount": 0,
            },
        ]
        result = parse_ability_metrics(
            entries, fight_id=1, player_name="Priest",
            metric_type="healing",
        )
        assert len(result) == 1
        # overheal=0 is treated as None (falsy)
        assert result[0].overheal_total is None
