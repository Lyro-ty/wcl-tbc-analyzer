"""Test that all raw SQL queries are syntactically valid against real PostgreSQL.

These tests execute each query against an empty (but schema-correct) database.
Queries may return no rows — that's fine — but they must not raise SQL errors.
"""

import pytest

from shukketsu.db import queries as q


@pytest.mark.integration
async def test_my_performance_query(session):
    """MY_PERFORMANCE query executes without syntax error."""
    await session.execute(
        q.MY_PERFORMANCE, {"encounter_name": "%test%", "player_name": "%test%"}
    )


@pytest.mark.integration
async def test_top_rankings_query(session):
    """TOP_RANKINGS query executes without syntax error."""
    await session.execute(
        q.TOP_RANKINGS,
        {"encounter_name": "%test%", "class_name": "%Warrior%", "spec_name": "%Arms%"},
    )


@pytest.mark.integration
async def test_compare_to_top_query(session):
    """COMPARE_TO_TOP query executes without syntax error."""
    await session.execute(
        q.COMPARE_TO_TOP,
        {
            "encounter_name": "%test%",
            "player_name": "%test%",
            "class_name": "%Warrior%",
            "spec_name": "%Arms%",
        },
    )


@pytest.mark.integration
async def test_fight_details_query(session):
    """FIGHT_DETAILS query executes without syntax error."""
    await session.execute(q.FIGHT_DETAILS, {"report_code": "test", "fight_id": 0})


@pytest.mark.integration
async def test_progression_query(session):
    """PROGRESSION query executes without syntax error."""
    await session.execute(
        q.PROGRESSION, {"character_name": "%test%", "encounter_name": "%test%"}
    )


@pytest.mark.integration
async def test_deaths_and_mechanics_query(session):
    """DEATHS_AND_MECHANICS query executes without syntax error."""
    await session.execute(q.DEATHS_AND_MECHANICS, {"encounter_name": "%test%"})


@pytest.mark.integration
async def test_raid_summary_query(session):
    """RAID_SUMMARY query executes without syntax error."""
    await session.execute(q.RAID_SUMMARY, {"report_code": "test"})


@pytest.mark.integration
async def test_search_fights_query(session):
    """SEARCH_FIGHTS query executes without syntax error."""
    await session.execute(q.SEARCH_FIGHTS, {"encounter_name": "%test%"})


@pytest.mark.integration
async def test_raid_vs_top_speed_query(session):
    """RAID_VS_TOP_SPEED query with CTEs and PERCENTILE_CONT executes."""
    await session.execute(q.RAID_VS_TOP_SPEED, {"report_code": "test"})


@pytest.mark.integration
async def test_compare_two_raids_query(session):
    """COMPARE_TWO_RAIDS query with FULL OUTER JOIN executes."""
    await session.execute(
        q.COMPARE_TWO_RAIDS, {"report_a": "test_a", "report_b": "test_b"}
    )


@pytest.mark.integration
async def test_raid_execution_summary_query(session):
    """RAID_EXECUTION_SUMMARY query executes without syntax error."""
    await session.execute(q.RAID_EXECUTION_SUMMARY, {"report_code": "test"})


@pytest.mark.integration
async def test_spec_leaderboard_query(session):
    """SPEC_LEADERBOARD query with PERCENTILE_CONT and HAVING executes."""
    await session.execute(q.SPEC_LEADERBOARD, {"encounter_name": "%test%"})


@pytest.mark.integration
async def test_reports_list_query(session):
    """REPORTS_LIST query (no params) executes without syntax error."""
    await session.execute(q.REPORTS_LIST)


@pytest.mark.integration
async def test_encounters_list_query(session):
    """ENCOUNTERS_LIST query (no params) executes without syntax error."""
    await session.execute(q.ENCOUNTERS_LIST)


@pytest.mark.integration
async def test_characters_list_query(session):
    """CHARACTERS_LIST query (no params) executes without syntax error."""
    await session.execute(q.CHARACTERS_LIST)


@pytest.mark.integration
async def test_character_reports_query(session):
    """CHARACTER_REPORTS query executes without syntax error."""
    await session.execute(q.CHARACTER_REPORTS, {"character_name": "%test%"})


@pytest.mark.integration
async def test_report_deaths_query(session):
    """REPORT_DEATHS query executes without syntax error."""
    await session.execute(q.REPORT_DEATHS, {"report_code": "test"})


@pytest.mark.integration
async def test_ability_breakdown_query(session):
    """ABILITY_BREAKDOWN query executes without syntax error."""
    await session.execute(
        q.ABILITY_BREAKDOWN,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_buff_analysis_query(session):
    """BUFF_ANALYSIS query executes without syntax error."""
    await session.execute(
        q.BUFF_ANALYSIS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_death_analysis_query(session):
    """DEATH_ANALYSIS query with CAST(:player_name AS text) executes."""
    await session.execute(
        q.DEATH_ANALYSIS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cast_activity_query(session):
    """CAST_ACTIVITY query with CAST(:player_name AS text) executes."""
    await session.execute(
        q.CAST_ACTIVITY,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cooldown_efficiency_query(session):
    """COOLDOWN_EFFICIENCY query executes without syntax error."""
    await session.execute(
        q.COOLDOWN_EFFICIENCY,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cancelled_casts_query(session):
    """CANCELLED_CASTS query executes without syntax error."""
    await session.execute(
        q.CANCELLED_CASTS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_consumable_check_query(session):
    """CONSUMABLE_CHECK query with CAST(:player_name AS text) executes."""
    await session.execute(
        q.CONSUMABLE_CHECK,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_resource_usage_query(session):
    """RESOURCE_USAGE query executes without syntax error."""
    await session.execute(
        q.RESOURCE_USAGE,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_wipe_progression_query(session):
    """WIPE_PROGRESSION query with subquery executes."""
    await session.execute(
        q.WIPE_PROGRESSION, {"report_code": "test", "encounter_name": "%test%"}
    )


@pytest.mark.integration
async def test_regression_check_query(session):
    """REGRESSION_CHECK query with CTEs and window functions executes."""
    await session.execute(q.REGRESSION_CHECK)


@pytest.mark.integration
async def test_regression_check_player_query(session):
    """REGRESSION_CHECK_PLAYER query executes without syntax error."""
    await session.execute(q.REGRESSION_CHECK_PLAYER, {"player_name": "%test%"})


@pytest.mark.integration
async def test_my_recent_kills_query(session):
    """MY_RECENT_KILLS query with optional CAST param executes."""
    await session.execute(
        q.MY_RECENT_KILLS, {"encounter_name": None, "limit": 10}
    )


@pytest.mark.integration
async def test_personal_bests_query(session):
    """PERSONAL_BESTS query executes without syntax error."""
    await session.execute(q.PERSONAL_BESTS, {"player_name": "%test%"})


@pytest.mark.integration
async def test_personal_bests_by_encounter_query(session):
    """PERSONAL_BESTS_BY_ENCOUNTER query executes without syntax error."""
    await session.execute(
        q.PERSONAL_BESTS_BY_ENCOUNTER,
        {"player_name": "%test%", "encounter_name": "%test%"},
    )


@pytest.mark.integration
async def test_dashboard_stats_query(session):
    """DASHBOARD_STATS query (no params) with subqueries executes."""
    await session.execute(q.DASHBOARD_STATS)


@pytest.mark.integration
async def test_recent_reports_query(session):
    """RECENT_REPORTS query with FILTER clause executes."""
    await session.execute(q.RECENT_REPORTS)


@pytest.mark.integration
async def test_character_profile_query(session):
    """CHARACTER_PROFILE query executes without syntax error."""
    await session.execute(q.CHARACTER_PROFILE, {"character_name": "%test%"})


@pytest.mark.integration
async def test_character_recent_parses_query(session):
    """CHARACTER_RECENT_PARSES query executes without syntax error."""
    await session.execute(q.CHARACTER_RECENT_PARSES, {"character_name": "%test%"})


@pytest.mark.integration
async def test_gear_snapshot_query(session):
    """GEAR_SNAPSHOT query executes without syntax error."""
    await session.execute(
        q.GEAR_SNAPSHOT,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_gear_changes_query(session):
    """GEAR_CHANGES query with FULL OUTER JOIN and IS DISTINCT FROM executes."""
    await session.execute(
        q.GEAR_CHANGES,
        {
            "report_code_old": "test_old",
            "report_code_new": "test_new",
            "player_name": "%test%",
        },
    )


@pytest.mark.integration
async def test_overheal_analysis_query(session):
    """OVERHEAL_ANALYSIS query with CASE expression executes."""
    await session.execute(
        q.OVERHEAL_ANALYSIS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cast_timeline_query(session):
    """CAST_TIMELINE query executes without syntax error."""
    await session.execute(
        q.CAST_TIMELINE,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cooldown_windows_query(session):
    """COOLDOWN_WINDOWS query with multi-table JOIN executes."""
    await session.execute(
        q.COOLDOWN_WINDOWS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_enchant_gem_check_query(session):
    """ENCHANT_GEM_CHECK query executes without syntax error."""
    await session.execute(
        q.ENCHANT_GEM_CHECK,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_phase_breakdown_query(session):
    """PHASE_BREAKDOWN query with CAST(:player_name AS text) executes."""
    await session.execute(
        q.PHASE_BREAKDOWN,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_week_over_week_query(session):
    """WEEK_OVER_WEEK query with CTEs and subqueries executes."""
    await session.execute(q.WEEK_OVER_WEEK, {"report_code": "test"})


@pytest.mark.integration
async def test_night_summary_fights_query(session):
    """NIGHT_SUMMARY_FIGHTS query executes without syntax error."""
    await session.execute(q.NIGHT_SUMMARY_FIGHTS, {"report_code": "test"})


@pytest.mark.integration
async def test_night_summary_players_query(session):
    """NIGHT_SUMMARY_PLAYERS query executes without syntax error."""
    await session.execute(q.NIGHT_SUMMARY_PLAYERS, {"report_code": "test"})


@pytest.mark.integration
async def test_player_parse_deltas_query(session):
    """PLAYER_PARSE_DELTAS query with CTEs executes."""
    await session.execute(q.PLAYER_PARSE_DELTAS, {"report_code": "test"})


@pytest.mark.integration
async def test_table_data_exists_query(session):
    """TABLE_DATA_EXISTS query executes without syntax error."""
    await session.execute(q.TABLE_DATA_EXISTS, {"report_code": "test"})


@pytest.mark.integration
async def test_event_data_exists_query(session):
    """EVENT_DATA_EXISTS query with multiple EXISTS clauses executes."""
    await session.execute(q.EVENT_DATA_EXISTS, {"report_code": "test"})


@pytest.mark.integration
async def test_character_report_detail_query(session):
    """CHARACTER_REPORT_DETAIL query executes without syntax error."""
    await session.execute(
        q.CHARACTER_REPORT_DETAIL,
        {"report_code": "test", "character_name": "%test%"},
    )


@pytest.mark.integration
async def test_fight_deaths_query(session):
    """FIGHT_DEATHS query executes without syntax error."""
    await session.execute(
        q.FIGHT_DEATHS, {"report_code": "test", "fight_id": 0}
    )


@pytest.mark.integration
async def test_fight_cast_metrics_query(session):
    """FIGHT_CAST_METRICS query executes without syntax error."""
    await session.execute(
        q.FIGHT_CAST_METRICS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_fight_cooldowns_query(session):
    """FIGHT_COOLDOWNS query executes without syntax error."""
    await session.execute(
        q.FIGHT_COOLDOWNS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_fight_abilities_query(session):
    """FIGHT_ABILITIES query (all players) executes without syntax error."""
    await session.execute(
        q.FIGHT_ABILITIES, {"report_code": "test", "fight_id": 0}
    )


@pytest.mark.integration
async def test_fight_abilities_player_query(session):
    """FIGHT_ABILITIES_PLAYER query executes without syntax error."""
    await session.execute(
        q.FIGHT_ABILITIES_PLAYER,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_fight_buffs_query(session):
    """FIGHT_BUFFS query (all players) executes without syntax error."""
    await session.execute(
        q.FIGHT_BUFFS, {"report_code": "test", "fight_id": 0}
    )


@pytest.mark.integration
async def test_fight_buffs_player_query(session):
    """FIGHT_BUFFS_PLAYER query executes without syntax error."""
    await session.execute(
        q.FIGHT_BUFFS_PLAYER,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cast_events_for_dot_analysis_query(session):
    """CAST_EVENTS_FOR_DOT_ANALYSIS query executes without syntax error."""
    await session.execute(
        q.CAST_EVENTS_FOR_DOT_ANALYSIS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_player_fight_info_query(session):
    """PLAYER_FIGHT_INFO query executes without syntax error."""
    await session.execute(
        q.PLAYER_FIGHT_INFO,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_player_buffs_for_trinkets_query(session):
    """PLAYER_BUFFS_FOR_TRINKETS query executes without syntax error."""
    await session.execute(
        q.PLAYER_BUFFS_FOR_TRINKETS,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_cast_events_for_phases_query(session):
    """CAST_EVENTS_FOR_PHASES query executes without syntax error."""
    await session.execute(
        q.CAST_EVENTS_FOR_PHASES,
        {"report_code": "test", "fight_id": 0, "player_name": "%test%"},
    )


@pytest.mark.integration
async def test_raid_ability_summary_query(session):
    """RAID_ABILITY_SUMMARY query executes without syntax error."""
    await session.execute(
        q.RAID_ABILITY_SUMMARY, {"report_code": "test", "fight_id": 0}
    )
