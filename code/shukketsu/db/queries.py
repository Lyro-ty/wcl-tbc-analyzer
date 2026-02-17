"""Analytical SQL queries for the agent tools."""

from sqlalchemy import text

MY_PERFORMANCE = text("""
    SELECT fp.player_name, fp.player_class, fp.player_spec,
           fp.dps, fp.hps, fp.parse_percentile, fp.ilvl_parse_percentile,
           fp.deaths, fp.interrupts, fp.dispels, fp.item_level,
           e.name AS encounter_name, f.kill, f.duration_ms
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE e.name ILIKE :encounter_name
      AND fp.player_name ILIKE :player_name
    ORDER BY f.end_time DESC
    LIMIT 10
""")

TOP_RANKINGS = text("""
    SELECT tr.player_name, tr.player_server, tr.amount, tr.duration_ms,
           tr.guild_name, tr.item_level, tr.rank_position
    FROM top_rankings tr
    JOIN encounters e ON tr.encounter_id = e.id
    WHERE e.name ILIKE :encounter_name
      AND tr.class ILIKE :class_name
      AND tr.spec ILIKE :spec_name
    ORDER BY tr.rank_position ASC
    LIMIT 10
""")

COMPARE_TO_TOP = text("""
    WITH my_perf AS (
        SELECT fp.dps, fp.parse_percentile, fp.item_level, fp.deaths,
               fp.player_class, fp.player_spec
        FROM fight_performances fp
        JOIN fights f ON fp.fight_id = f.id
        JOIN encounters e ON f.encounter_id = e.id
        WHERE e.name ILIKE :encounter_name
          AND fp.player_name ILIKE :player_name
        ORDER BY f.end_time DESC
        LIMIT 1
    ),
    top_perf AS (
        SELECT AVG(tr.amount) AS avg_dps, AVG(tr.item_level) AS avg_ilvl,
               MIN(tr.amount) AS min_dps, MAX(tr.amount) AS max_dps
        FROM top_rankings tr
        JOIN encounters e ON tr.encounter_id = e.id
        WHERE e.name ILIKE :encounter_name
          AND tr.class ILIKE :class_name
          AND tr.spec ILIKE :spec_name
          AND tr.rank_position <= 10
    )
    SELECT * FROM my_perf, top_perf
""")

FIGHT_DETAILS = text("""
    SELECT fp.player_name, fp.player_class, fp.player_spec,
           fp.dps, fp.hps, fp.parse_percentile, fp.deaths,
           fp.interrupts, fp.dispels, fp.item_level,
           f.kill, f.duration_ms,
           e.name AS encounter_name, r.title AS report_title
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    JOIN reports r ON f.report_code = r.code
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
    ORDER BY fp.dps DESC
""")

PROGRESSION = text("""
    SELECT ps.time, ps.best_parse, ps.median_parse,
           ps.best_dps, ps.median_dps, ps.kill_count, ps.avg_deaths,
           e.name AS encounter_name, mc.name AS character_name
    FROM progression_snapshots ps
    JOIN my_characters mc ON ps.character_id = mc.id
    JOIN encounters e ON ps.encounter_id = e.id
    WHERE mc.name ILIKE :character_name
      AND e.name ILIKE :encounter_name
    ORDER BY ps.time ASC
""")

DEATHS_AND_MECHANICS = text("""
    SELECT fp.player_name, fp.player_class, fp.player_spec,
           fp.deaths, fp.interrupts, fp.dispels,
           e.name AS encounter_name, f.kill, f.duration_ms
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE e.name ILIKE :encounter_name
      AND (fp.deaths > 0 OR fp.interrupts > 0 OR fp.dispels > 0)
    ORDER BY fp.deaths DESC, fp.interrupts DESC, fp.dispels DESC, f.end_time DESC
    LIMIT 20
""")

RAID_SUMMARY = text("""
    SELECT f.fight_id, e.name AS encounter_name,
           f.kill, f.duration_ms,
           COUNT(fp.id) AS player_count
    FROM fights f
    JOIN encounters e ON f.encounter_id = e.id
    LEFT JOIN fight_performances fp ON fp.fight_id = f.id
    WHERE f.report_code = :report_code
    GROUP BY f.fight_id, e.name, f.kill, f.duration_ms
    ORDER BY f.fight_id ASC
""")

SEARCH_FIGHTS = text("""
    SELECT f.fight_id, f.report_code, e.name AS encounter_name,
           f.kill, f.duration_ms, r.title AS report_title,
           r.start_time AS report_start
    FROM fights f
    JOIN encounters e ON f.encounter_id = e.id
    JOIN reports r ON f.report_code = r.code
    WHERE e.name ILIKE :encounter_name
    ORDER BY r.start_time DESC
    LIMIT 20
""")

RAID_VS_TOP_SPEED = text("""
    WITH my_raid AS (
        SELECT f.fight_id, f.encounter_id, e.name AS encounter_name,
               f.duration_ms, f.kill,
               COUNT(fp.id) AS player_count,
               SUM(fp.deaths) AS total_deaths,
               SUM(fp.interrupts) AS total_interrupts,
               SUM(fp.dispels) AS total_dispels,
               ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps
        FROM fights f
        JOIN encounters e ON f.encounter_id = e.id
        LEFT JOIN fight_performances fp ON fp.fight_id = f.id
        WHERE f.report_code = :report_code
          AND f.kill = true
        GROUP BY f.fight_id, f.encounter_id, e.name, f.duration_ms, f.kill
    ),
    top_speeds AS (
        SELECT sr.encounter_id,
               MIN(sr.duration_ms) AS world_record_ms,
               ROUND(AVG(sr.duration_ms) FILTER (WHERE sr.rank_position <= 10)::numeric, 0)
                   AS top10_avg_ms,
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sr.duration_ms)::numeric, 0)
                   AS top100_median_ms
        FROM speed_rankings sr
        GROUP BY sr.encounter_id
    )
    SELECT mr.fight_id, mr.encounter_name, mr.duration_ms, mr.player_count,
           mr.total_deaths, mr.total_interrupts, mr.total_dispels, mr.avg_dps,
           ts.world_record_ms, ts.top10_avg_ms, ts.top100_median_ms
    FROM my_raid mr
    LEFT JOIN top_speeds ts ON mr.encounter_id = ts.encounter_id
    ORDER BY mr.fight_id ASC
""")

COMPARE_TWO_RAIDS = text("""
    WITH raid_a AS (
        SELECT f.encounter_id, e.name AS encounter_name,
               f.duration_ms, f.kill,
               COUNT(fp.id) AS player_count,
               SUM(fp.deaths) AS total_deaths,
               SUM(fp.interrupts) AS total_interrupts,
               SUM(fp.dispels) AS total_dispels,
               ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
               STRING_AGG(DISTINCT fp.player_spec || ' ' || fp.player_class, ', '
                   ORDER BY fp.player_spec || ' ' || fp.player_class) AS composition
        FROM fights f
        JOIN encounters e ON f.encounter_id = e.id
        LEFT JOIN fight_performances fp ON fp.fight_id = f.id
        WHERE f.report_code = :report_a
          AND f.kill = true
        GROUP BY f.encounter_id, e.name, f.duration_ms, f.kill
    ),
    raid_b AS (
        SELECT f.encounter_id, e.name AS encounter_name,
               f.duration_ms, f.kill,
               COUNT(fp.id) AS player_count,
               SUM(fp.deaths) AS total_deaths,
               SUM(fp.interrupts) AS total_interrupts,
               SUM(fp.dispels) AS total_dispels,
               ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
               STRING_AGG(DISTINCT fp.player_spec || ' ' || fp.player_class, ', '
                   ORDER BY fp.player_spec || ' ' || fp.player_class) AS composition
        FROM fights f
        JOIN encounters e ON f.encounter_id = e.id
        LEFT JOIN fight_performances fp ON fp.fight_id = f.id
        WHERE f.report_code = :report_b
          AND f.kill = true
        GROUP BY f.encounter_id, e.name, f.duration_ms, f.kill
    )
    SELECT COALESCE(a.encounter_name, b.encounter_name) AS encounter_name,
           a.duration_ms AS a_duration_ms, b.duration_ms AS b_duration_ms,
           a.total_deaths AS a_deaths, b.total_deaths AS b_deaths,
           a.total_interrupts AS a_interrupts, b.total_interrupts AS b_interrupts,
           a.total_dispels AS a_dispels, b.total_dispels AS b_dispels,
           a.avg_dps AS a_avg_dps, b.avg_dps AS b_avg_dps,
           a.player_count AS a_players, b.player_count AS b_players,
           a.composition AS a_comp, b.composition AS b_comp
    FROM raid_a a
    FULL OUTER JOIN raid_b b ON a.encounter_id = b.encounter_id
    ORDER BY COALESCE(a.encounter_name, b.encounter_name)
""")

RAID_EXECUTION_SUMMARY = text("""
    SELECT e.name AS encounter_name, f.fight_id,
           f.duration_ms,
           COUNT(fp.id) AS player_count,
           SUM(fp.deaths) AS total_deaths,
           ROUND(AVG(fp.deaths)::numeric, 2) AS avg_deaths_per_player,
           SUM(fp.interrupts) AS total_interrupts,
           SUM(fp.dispels) AS total_dispels,
           ROUND(AVG(fp.dps)::numeric, 1) AS raid_avg_dps,
           ROUND(SUM(fp.dps)::numeric, 1) AS raid_total_dps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           ROUND(AVG(fp.item_level)::numeric, 1) AS avg_ilvl
    FROM fights f
    JOIN encounters e ON f.encounter_id = e.id
    LEFT JOIN fight_performances fp ON fp.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.kill = true
    GROUP BY e.name, f.fight_id, f.duration_ms
    ORDER BY f.fight_id ASC
""")

SPEC_LEADERBOARD = text("""
    SELECT fp.player_class, fp.player_spec,
           COUNT(*) AS sample_size,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(MAX(fp.dps)::numeric, 1) AS max_dps,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.dps)::numeric, 1) AS median_dps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           ROUND(AVG(fp.item_level)::numeric, 1) AS avg_ilvl
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE e.name ILIKE :encounter_name
      AND f.kill = true
      AND fp.dps > 0
    GROUP BY fp.player_class, fp.player_spec
    HAVING COUNT(*) >= 3
    ORDER BY avg_dps DESC
""")

REPORTS_LIST = text("""
    SELECT r.code, r.title, r.guild_name, r.start_time, r.end_time,
           COUNT(DISTINCT f.id) AS fight_count,
           COUNT(DISTINCT f.encounter_id) AS boss_count
    FROM reports r
    LEFT JOIN fights f ON f.report_code = r.code
    GROUP BY r.code, r.title, r.guild_name, r.start_time, r.end_time
    ORDER BY r.start_time DESC
""")

ENCOUNTERS_LIST = text("""
    SELECT e.id, e.name, e.zone_id, e.zone_name,
           COUNT(f.id) AS fight_count
    FROM encounters e
    LEFT JOIN fights f ON f.encounter_id = e.id
    GROUP BY e.id, e.name, e.zone_id, e.zone_name
    ORDER BY e.zone_name, e.name
""")

CHARACTERS_LIST = text("""
    SELECT mc.id, mc.name, mc.server_slug, mc.server_region,
           mc.character_class, mc.spec
    FROM my_characters mc
    ORDER BY mc.name
""")

CHARACTER_REPORTS = text("""
    SELECT r.code, r.title, r.guild_name, r.start_time, r.end_time,
           COUNT(DISTINCT f.id) AS fight_count,
           SUM(CASE WHEN f.kill THEN 1 ELSE 0 END) AS kill_count,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           SUM(fp.deaths) AS total_deaths
    FROM reports r
    JOIN fights f ON r.code = f.report_code
    JOIN fight_performances fp ON f.id = fp.fight_id
    WHERE fp.player_name = :character_name
    GROUP BY r.code, r.title, r.guild_name, r.start_time, r.end_time
    ORDER BY r.start_time DESC
""")

REPORT_DEATHS = text("""
    SELECT f.fight_id, e.name AS encounter_name,
           fp.player_name, fp.player_class, fp.player_spec,
           fp.deaths, fp.interrupts, fp.dispels
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND fp.deaths > 0
    ORDER BY f.fight_id ASC, fp.deaths DESC
""")

ABILITY_BREAKDOWN = text("""
    SELECT am.player_name, am.metric_type, am.ability_name, am.spell_id,
           am.total, am.hit_count, am.crit_count, am.crit_pct, am.pct_of_total
    FROM ability_metrics am
    JOIN fights f ON am.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND am.player_name ILIKE :player_name
    ORDER BY am.metric_type, am.pct_of_total DESC
""")

BUFF_ANALYSIS = text("""
    SELECT bu.player_name, bu.metric_type, bu.ability_name, bu.spell_id,
           bu.uptime_pct, bu.stack_count
    FROM buff_uptimes bu
    JOIN fights f ON bu.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND bu.player_name ILIKE :player_name
    ORDER BY bu.metric_type, bu.uptime_pct DESC
""")

RAID_ABILITY_SUMMARY = text("""
    SELECT am.player_name, am.ability_name, am.spell_id,
           am.total, am.pct_of_total, am.crit_pct
    FROM ability_metrics am
    JOIN fights f ON am.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND am.metric_type = 'damage'
      AND am.pct_of_total >= 5.0
    ORDER BY am.total DESC
""")

FIGHT_ABILITIES = text("""
    SELECT am.player_name, am.metric_type, am.ability_name, am.spell_id,
           am.total, am.hit_count, am.crit_count, am.crit_pct, am.pct_of_total
    FROM ability_metrics am
    JOIN fights f ON am.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
    ORDER BY am.player_name, am.metric_type, am.pct_of_total DESC
""")

FIGHT_ABILITIES_PLAYER = text("""
    SELECT am.player_name, am.metric_type, am.ability_name, am.spell_id,
           am.total, am.hit_count, am.crit_count, am.crit_pct, am.pct_of_total
    FROM ability_metrics am
    JOIN fights f ON am.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND am.player_name = :player_name
    ORDER BY am.metric_type, am.pct_of_total DESC
""")

FIGHT_BUFFS = text("""
    SELECT bu.player_name, bu.metric_type, bu.ability_name, bu.spell_id,
           bu.uptime_pct, bu.stack_count
    FROM buff_uptimes bu
    JOIN fights f ON bu.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
    ORDER BY bu.player_name, bu.metric_type, bu.uptime_pct DESC
""")

FIGHT_BUFFS_PLAYER = text("""
    SELECT bu.player_name, bu.metric_type, bu.ability_name, bu.spell_id,
           bu.uptime_pct, bu.stack_count
    FROM buff_uptimes bu
    JOIN fights f ON bu.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND bu.player_name = :player_name
    ORDER BY bu.metric_type, bu.uptime_pct DESC
""")

TABLE_DATA_EXISTS = text("""
    SELECT EXISTS(
        SELECT 1 FROM ability_metrics am
        JOIN fights f ON am.fight_id = f.id
        WHERE f.report_code = :report_code
    ) AS has_data
""")

EVENT_DATA_EXISTS = text("""
    SELECT EXISTS(
        SELECT 1 FROM death_details dd
        JOIN fights f ON dd.fight_id = f.id
        WHERE f.report_code = :report_code
    ) AS has_data
""")

DEATH_ANALYSIS = text("""
    SELECT dd.player_name, dd.death_index, dd.timestamp_ms,
           dd.killing_blow_ability, dd.killing_blow_source,
           dd.damage_taken_total, dd.events_json,
           e.name AS encounter_name, f.fight_id, f.duration_ms
    FROM death_details dd
    JOIN fights f ON dd.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND (:player_name IS NULL OR dd.player_name ILIKE :player_name)
    ORDER BY dd.timestamp_ms ASC, dd.death_index ASC
""")

CAST_ACTIVITY = text("""
    SELECT cm.player_name, cm.total_casts, cm.casts_per_minute,
           cm.gcd_uptime_pct, cm.active_time_ms, cm.downtime_ms,
           cm.longest_gap_ms, cm.longest_gap_at_ms, cm.avg_gap_ms, cm.gap_count,
           e.name AS encounter_name, f.fight_id, f.duration_ms
    FROM cast_metrics cm
    JOIN fights f ON cm.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND (:player_name IS NULL OR cm.player_name ILIKE :player_name)
    ORDER BY cm.gcd_uptime_pct DESC
""")

COOLDOWN_EFFICIENCY = text("""
    SELECT cu.player_name, cu.ability_name, cu.spell_id, cu.cooldown_sec,
           cu.times_used, cu.max_possible_uses, cu.first_use_ms, cu.last_use_ms,
           cu.efficiency_pct,
           e.name AS encounter_name, f.fight_id, f.duration_ms
    FROM cooldown_usage cu
    JOIN fights f ON cu.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND (:player_name IS NULL OR cu.player_name ILIKE :player_name)
    ORDER BY cu.player_name, cu.efficiency_pct ASC
""")

CHARACTER_PROFILE = text("""
    SELECT mc.id, mc.name, mc.server_slug, mc.server_region,
           mc.character_class, mc.spec,
           COUNT(fp.id) AS total_fights,
           SUM(CASE WHEN f.kill THEN 1 ELSE 0 END) AS total_kills,
           COALESCE(SUM(fp.deaths), 0) AS total_deaths,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(MAX(fp.dps)::numeric, 1) AS best_dps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           ROUND(MAX(fp.parse_percentile)::numeric, 1) AS best_parse,
           ROUND(AVG(fp.item_level)::numeric, 1) AS avg_ilvl
    FROM my_characters mc
    LEFT JOIN fight_performances fp ON fp.player_name = mc.name
    LEFT JOIN fights f ON fp.fight_id = f.id
    WHERE mc.name = :character_name
    GROUP BY mc.id, mc.name, mc.server_slug, mc.server_region,
             mc.character_class, mc.spec
""")

CHARACTER_RECENT_PARSES = text("""
    SELECT e.name AS encounter_name, fp.dps, fp.hps,
           fp.parse_percentile, fp.deaths, fp.item_level,
           fp.player_class, fp.player_spec,
           f.kill, f.duration_ms, f.report_code, f.fight_id,
           r.start_time AS report_date
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    JOIN reports r ON f.report_code = r.code
    JOIN my_characters mc ON mc.name = fp.player_name
    WHERE mc.name = :character_name
    ORDER BY r.start_time DESC
    LIMIT 30
""")

DASHBOARD_STATS = text("""
    SELECT
        (SELECT COUNT(*) FROM reports) AS total_reports,
        (SELECT COUNT(*) FROM fights WHERE kill = true) AS total_kills,
        (SELECT COUNT(*) FROM fights WHERE kill = false) AS total_wipes,
        (SELECT COUNT(*) FROM my_characters) AS total_characters,
        (SELECT COUNT(DISTINCT encounter_id) FROM fights) AS total_encounters
""")

RECENT_REPORTS = text("""
    SELECT r.code, r.title, r.guild_name, r.start_time,
           COUNT(DISTINCT f.id) AS fight_count,
           SUM(CASE WHEN f.kill THEN 1 ELSE 0 END) AS kill_count,
           SUM(CASE WHEN NOT f.kill THEN 1 ELSE 0 END) AS wipe_count,
           ROUND(AVG(fp.dps) FILTER (WHERE f.kill)::numeric, 1) AS avg_kill_dps
    FROM reports r
    LEFT JOIN fights f ON f.report_code = r.code
    LEFT JOIN fight_performances fp ON fp.fight_id = f.id
    GROUP BY r.code, r.title, r.guild_name, r.start_time
    ORDER BY r.start_time DESC
    LIMIT 5
""")

CHARACTER_REPORT_DETAIL = text("""
    SELECT f.fight_id, e.name AS encounter_name, f.kill, f.duration_ms,
           fp.dps, fp.hps, fp.parse_percentile, fp.deaths,
           fp.interrupts, fp.dispels, fp.item_level,
           fp.player_class, fp.player_spec
    FROM fights f
    JOIN fight_performances fp ON f.id = fp.fight_id
    LEFT JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND fp.player_name = :character_name
    ORDER BY f.start_time
""")

FIGHT_DEATHS = text("""
    SELECT dd.player_name, dd.death_index, dd.timestamp_ms,
           dd.killing_blow_ability, dd.killing_blow_source,
           dd.damage_taken_total, dd.events_json
    FROM death_details dd
    JOIN fights f ON dd.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
    ORDER BY dd.timestamp_ms ASC, dd.death_index ASC
""")

FIGHT_CAST_METRICS = text("""
    SELECT cm.player_name, cm.total_casts, cm.casts_per_minute,
           cm.gcd_uptime_pct, cm.active_time_ms, cm.downtime_ms,
           cm.longest_gap_ms, cm.longest_gap_at_ms, cm.avg_gap_ms, cm.gap_count
    FROM cast_metrics cm
    JOIN fights f ON cm.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cm.player_name = :player_name
""")

FIGHT_COOLDOWNS = text("""
    SELECT cu.player_name, cu.ability_name, cu.spell_id, cu.cooldown_sec,
           cu.times_used, cu.max_possible_uses, cu.first_use_ms, cu.last_use_ms,
           cu.efficiency_pct
    FROM cooldown_usage cu
    JOIN fights f ON cu.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cu.player_name = :player_name
    ORDER BY cu.efficiency_pct ASC
""")

OVERHEAL_ANALYSIS = text("""
    SELECT am.player_name, am.ability_name, am.spell_id,
           am.total, am.overheal_total,
           CASE WHEN (am.total + COALESCE(am.overheal_total, 0)) > 0
                THEN ROUND(
                    (COALESCE(am.overheal_total, 0)::numeric
                     / (am.total + COALESCE(am.overheal_total, 0))::numeric) * 100, 1)
                ELSE 0 END AS overheal_pct
    FROM ability_metrics am
    JOIN fights f ON am.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND am.player_name ILIKE :player_name
      AND am.metric_type = 'healing'
      AND am.total > 0
    ORDER BY am.total DESC
""")

CANCELLED_CASTS = text("""
    SELECT cc.player_name, cc.total_begins, cc.total_completions,
           cc.cancel_count, cc.cancel_pct, cc.top_cancelled_json
    FROM cancelled_casts cc
    JOIN fights f ON cc.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cc.player_name = :player_name
""")

PERSONAL_BESTS = text("""
    SELECT e.name AS encounter_name,
           MAX(fp.dps) AS best_dps,
           MAX(fp.parse_percentile) AS best_parse,
           MAX(fp.hps) AS best_hps,
           COUNT(*) AS kill_count,
           MAX(fp.item_level) AS peak_ilvl
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE fp.player_name ILIKE :player_name
      AND f.kill = true
    GROUP BY e.id, e.name
    ORDER BY e.name
""")

PERSONAL_BESTS_BY_ENCOUNTER = text("""
    SELECT e.name AS encounter_name,
           MAX(fp.dps) AS best_dps,
           MAX(fp.parse_percentile) AS best_parse,
           MAX(fp.hps) AS best_hps,
           COUNT(*) AS kill_count,
           MAX(fp.item_level) AS peak_ilvl
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE fp.player_name ILIKE :player_name
      AND f.kill = true
      AND e.name ILIKE :encounter_name
    GROUP BY e.id, e.name
    ORDER BY e.name
""")

WIPE_PROGRESSION = text("""
    SELECT f.fight_id,
           f.kill,
           f.fight_percentage,
           f.duration_ms,
           COUNT(fp.id) AS player_count,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           SUM(fp.deaths) AS total_deaths,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse
    FROM fights f
    JOIN fight_performances fp ON f.id = fp.fight_id
    WHERE f.report_code = :report_code
      AND f.encounter_id = (
          SELECT id FROM encounters WHERE name ILIKE :encounter_name LIMIT 1
      )
    GROUP BY f.id, f.fight_id, f.kill, f.fight_percentage, f.duration_ms
    ORDER BY f.fight_id
""")

CONSUMABLE_CHECK = text("""
    SELECT fc.player_name, fc.category, fc.ability_name, fc.spell_id, fc.active
    FROM fight_consumables fc
    JOIN fights f ON fc.fight_id = f.id
    WHERE f.report_code = :report_code AND f.fight_id = :fight_id
      AND (:player_name IS NULL OR fc.player_name ILIKE :player_name)
    ORDER BY fc.player_name, fc.category
""")

REGRESSION_CHECK = text("""
    WITH ranked_fights AS (
        SELECT fp.player_name, e.name AS encounter_name,
               fp.dps, fp.parse_percentile,
               f.end_time,
               ROW_NUMBER() OVER (
                   PARTITION BY fp.player_name, e.id
                   ORDER BY f.end_time DESC
               ) AS rn
        FROM fight_performances fp
        JOIN fights f ON fp.fight_id = f.id
        JOIN encounters e ON f.encounter_id = e.id
        WHERE fp.is_my_character = true AND f.kill = true
    ),
    baseline AS (
        SELECT player_name, encounter_name,
               AVG(parse_percentile) AS baseline_parse,
               AVG(dps) AS baseline_dps
        FROM ranked_fights WHERE rn BETWEEN 3 AND 7
        GROUP BY player_name, encounter_name
        HAVING COUNT(*) >= 3
    ),
    recent AS (
        SELECT player_name, encounter_name,
               AVG(parse_percentile) AS recent_parse,
               AVG(dps) AS recent_dps
        FROM ranked_fights WHERE rn BETWEEN 1 AND 2
        GROUP BY player_name, encounter_name
    )
    SELECT r.player_name, r.encounter_name,
           ROUND(r.recent_parse::numeric, 1) AS recent_parse,
           ROUND(b.baseline_parse::numeric, 1) AS baseline_parse,
           ROUND(r.recent_dps::numeric, 1) AS recent_dps,
           ROUND(b.baseline_dps::numeric, 1) AS baseline_dps,
           ROUND((r.recent_parse - b.baseline_parse)::numeric, 1) AS parse_delta,
           ROUND(((r.recent_dps - b.baseline_dps)
               / NULLIF(b.baseline_dps, 0) * 100)::numeric, 1) AS dps_delta_pct
    FROM recent r
    JOIN baseline b ON r.player_name = b.player_name
                   AND r.encounter_name = b.encounter_name
    WHERE ABS(r.recent_parse - b.baseline_parse) >= 15
    ORDER BY parse_delta ASC
""")

MY_RECENT_KILLS = text("""
    SELECT f.report_code, f.fight_id, e.name AS encounter_name,
           fp.dps, fp.parse_percentile, fp.deaths, fp.item_level,
           f.duration_ms, r.title AS report_title, r.start_time AS report_time
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    JOIN reports r ON f.report_code = r.code
    WHERE fp.is_my_character = true
      AND f.kill = true
      AND (:encounter_name IS NULL OR e.name ILIKE :encounter_name)
    ORDER BY r.start_time DESC, f.fight_id DESC
    LIMIT :limit
""")

GEAR_SNAPSHOT = text("""
    SELECT gs.slot, gs.item_id, gs.item_level, gs.player_name
    FROM gear_snapshots gs
    JOIN fights f ON gs.fight_id = f.id
    WHERE f.report_code = :report_code AND f.fight_id = :fight_id
      AND gs.player_name ILIKE :player_name
    ORDER BY gs.slot
""")

GEAR_CHANGES = text("""
    WITH old_gear AS (
        SELECT gs.slot, gs.item_id, gs.item_level
        FROM gear_snapshots gs
        JOIN fights f ON gs.fight_id = f.id
        WHERE f.report_code = :report_code_old
          AND gs.player_name ILIKE :player_name
          AND f.fight_id = (
              SELECT MIN(f2.fight_id) FROM fights f2
              WHERE f2.report_code = :report_code_old
          )
    ),
    new_gear AS (
        SELECT gs.slot, gs.item_id, gs.item_level
        FROM gear_snapshots gs
        JOIN fights f ON gs.fight_id = f.id
        WHERE f.report_code = :report_code_new
          AND gs.player_name ILIKE :player_name
          AND f.fight_id = (
              SELECT MIN(f2.fight_id) FROM fights f2
              WHERE f2.report_code = :report_code_new
          )
    )
    SELECT COALESCE(o.slot, n.slot) AS slot,
           o.item_id AS old_item_id, o.item_level AS old_ilvl,
           n.item_id AS new_item_id, n.item_level AS new_ilvl
    FROM old_gear o
    FULL OUTER JOIN new_gear n ON o.slot = n.slot
    WHERE o.item_id IS DISTINCT FROM n.item_id
    ORDER BY COALESCE(o.slot, n.slot)
""")

REGRESSION_CHECK_PLAYER = text("""
    WITH ranked_fights AS (
        SELECT fp.player_name, e.name AS encounter_name,
               fp.dps, fp.parse_percentile,
               f.end_time,
               ROW_NUMBER() OVER (
                   PARTITION BY fp.player_name, e.id
                   ORDER BY f.end_time DESC
               ) AS rn
        FROM fight_performances fp
        JOIN fights f ON fp.fight_id = f.id
        JOIN encounters e ON f.encounter_id = e.id
        WHERE fp.is_my_character = true AND f.kill = true
          AND fp.player_name ILIKE :player_name
    ),
    baseline AS (
        SELECT player_name, encounter_name,
               AVG(parse_percentile) AS baseline_parse,
               AVG(dps) AS baseline_dps
        FROM ranked_fights WHERE rn BETWEEN 3 AND 7
        GROUP BY player_name, encounter_name
        HAVING COUNT(*) >= 3
    ),
    recent AS (
        SELECT player_name, encounter_name,
               AVG(parse_percentile) AS recent_parse,
               AVG(dps) AS recent_dps
        FROM ranked_fights WHERE rn BETWEEN 1 AND 2
        GROUP BY player_name, encounter_name
    )
    SELECT r.player_name, r.encounter_name,
           ROUND(r.recent_parse::numeric, 1) AS recent_parse,
           ROUND(b.baseline_parse::numeric, 1) AS baseline_parse,
           ROUND(r.recent_dps::numeric, 1) AS recent_dps,
           ROUND(b.baseline_dps::numeric, 1) AS baseline_dps,
           ROUND((r.recent_parse - b.baseline_parse)::numeric, 1) AS parse_delta,
           ROUND(((r.recent_dps - b.baseline_dps)
               / NULLIF(b.baseline_dps, 0) * 100)::numeric, 1) AS dps_delta_pct
    FROM recent r
    JOIN baseline b ON r.player_name = b.player_name
                   AND r.encounter_name = b.encounter_name
    WHERE ABS(r.recent_parse - b.baseline_parse) >= 15
    ORDER BY parse_delta ASC
""")
