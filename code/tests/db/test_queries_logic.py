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

    def test_ctes_use_row_number_for_pairing(self):
        """CTEs must use ROW_NUMBER to pair kills across raids, not Cartesian."""
        sql = q.COMPARE_TWO_RAIDS.text
        assert "ROW_NUMBER()" in sql
        # JOIN must match on both encounter_id AND rn
        join_section = sql.split("FROM raid_a")[1]
        assert "a.rn = b.rn" in join_section


class TestRoleAwareQueries:
    """Verify key queries select hps alongside dps."""

    def test_my_performance_selects_hps(self):
        from shukketsu.db.queries.player import MY_PERFORMANCE
        query_text = MY_PERFORMANCE.text
        assert "fp.hps" in query_text

    def test_fight_details_selects_hps(self):
        from shukketsu.db.queries.player import FIGHT_DETAILS
        query_text = FIGHT_DETAILS.text
        assert "fp.hps" in query_text

    def test_spec_leaderboard_has_hps(self):
        """Leaderboard should include hps for healer ranking."""
        from shukketsu.db.queries.player import SPEC_LEADERBOARD
        query_text = SPEC_LEADERBOARD.text
        assert "hps" in query_text.lower()

    def test_raid_execution_has_hps(self):
        from shukketsu.db.queries.raid import RAID_EXECUTION_SUMMARY
        query_text = RAID_EXECUTION_SUMMARY.text
        assert "hps" in query_text.lower()

    def test_compare_to_top_has_hps(self):
        from shukketsu.db.queries.player import COMPARE_TO_TOP
        query_text = COMPARE_TO_TOP.text
        assert "fp.hps" in query_text

    def test_wipe_progression_has_hps(self):
        from shukketsu.db.queries.player import WIPE_PROGRESSION
        query_text = WIPE_PROGRESSION.text
        assert "hps" in query_text.lower()

    def test_my_recent_kills_has_hps(self):
        from shukketsu.db.queries.player import MY_RECENT_KILLS
        query_text = MY_RECENT_KILLS.text
        assert "fp.hps" in query_text

    def test_regression_check_has_hps(self):
        from shukketsu.db.queries.player import REGRESSION_CHECK
        query_text = REGRESSION_CHECK.text
        assert "hps" in query_text.lower()

    def test_compare_two_raids_has_hps(self):
        from shukketsu.db.queries.raid import COMPARE_TWO_RAIDS
        query_text = COMPARE_TWO_RAIDS.text
        assert "hps" in query_text.lower()

    def test_raid_vs_top_speed_has_hps(self):
        from shukketsu.db.queries.raid import RAID_VS_TOP_SPEED
        query_text = RAID_VS_TOP_SPEED.text
        assert "hps" in query_text.lower()

    def test_character_reports_has_hps(self):
        from shukketsu.db.queries.api import CHARACTER_REPORTS
        query_text = CHARACTER_REPORTS.text
        assert "hps" in query_text.lower()

    def test_character_profile_has_hps(self):
        from shukketsu.db.queries.api import CHARACTER_PROFILE
        query_text = CHARACTER_PROFILE.text
        assert "hps" in query_text.lower()

    def test_recent_reports_has_hps(self):
        from shukketsu.db.queries.api import RECENT_REPORTS
        query_text = RECENT_REPORTS.text
        assert "hps" in query_text.lower()

    def test_night_summary_fights_has_hps(self):
        from shukketsu.db.queries.api import NIGHT_SUMMARY_FIGHTS
        query_text = NIGHT_SUMMARY_FIGHTS.text
        assert "hps" in query_text.lower()

    def test_night_summary_players_has_hps(self):
        from shukketsu.db.queries.api import NIGHT_SUMMARY_PLAYERS
        query_text = NIGHT_SUMMARY_PLAYERS.text
        assert "fp.hps" in query_text


class TestGearChangesQuery:
    def test_uses_min_id_not_min_fight_id(self):
        """GEAR_CHANGES should use MIN(f2.id) for stable ordering."""
        sql = q.GEAR_CHANGES.text
        assert "MIN(f2.id)" in sql
        assert "MIN(f2.fight_id)" not in sql
