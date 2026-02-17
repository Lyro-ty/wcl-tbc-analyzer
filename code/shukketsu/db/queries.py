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
      AND fp.deaths > 0
    ORDER BY fp.deaths DESC, f.end_time DESC
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
