"""Unit tests that verify SQL query text correctness."""

from shukketsu.db import queries as q


class TestCompareTwoRaidsQuery:
    def test_raid_a_groups_by_fight_id(self):
        """raid_a CTE must GROUP BY f.id to avoid merging duplicate boss kills."""
        sql = q.COMPARE_TWO_RAIDS.text
        raid_a_section = sql.split("raid_b AS")[0]
        group_by = raid_a_section.split("GROUP BY")[1].strip()
        assert "f.id" in group_by

    def test_raid_b_groups_by_fight_id(self):
        """raid_b CTE must GROUP BY f.id to avoid merging duplicate boss kills."""
        sql = q.COMPARE_TWO_RAIDS.text
        raid_b_section = sql.split("raid_b AS")[1].split("SELECT COALESCE")[0]
        group_by = raid_b_section.split("GROUP BY")[1].strip()
        assert "f.id" in group_by
