"""Player and encounter-level SQL queries (13 queries).

Used by: agent/tools/player_tools.py, api/routes/data/characters.py,
         api/routes/data/rankings.py, api/routes/data/reports.py
"""

from sqlalchemy import text

__all__ = [
    "MY_PERFORMANCE",
    "TOP_RANKINGS",
    "COMPARE_TO_TOP",
    "FIGHT_DETAILS",
    "PROGRESSION",
    "DEATHS_AND_MECHANICS",
    "SEARCH_FIGHTS",
    "SPEC_LEADERBOARD",
    "PERSONAL_BESTS",
    "PERSONAL_BESTS_BY_ENCOUNTER",
    "WIPE_PROGRESSION",
    "REGRESSION_CHECK",
    "MY_RECENT_KILLS",
]

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
        SELECT fp.dps, fp.hps, fp.parse_percentile, fp.item_level, fp.deaths,
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
    LIMIT 50
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
    LIMIT 100
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

SPEC_LEADERBOARD = text("""
    SELECT fp.player_class, fp.player_spec,
           COUNT(*) AS sample_size,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(MAX(fp.dps)::numeric, 1) AS max_dps,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.dps)::numeric, 1) AS median_dps,
           ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
           ROUND(MAX(fp.hps)::numeric, 1) AS max_hps,
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
    LIMIT 50
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
           ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
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

REGRESSION_CHECK = text("""
    WITH ranked_fights AS (
        SELECT fp.player_name, e.name AS encounter_name,
               fp.dps, fp.hps, fp.parse_percentile,
               f.end_time,
               ROW_NUMBER() OVER (
                   PARTITION BY fp.player_name, e.id
                   ORDER BY f.end_time DESC
               ) AS rn
        FROM fight_performances fp
        JOIN fights f ON fp.fight_id = f.id
        JOIN encounters e ON f.encounter_id = e.id
        WHERE fp.is_my_character = true AND f.kill = true
          AND (CAST(:player_name AS text) IS NULL OR fp.player_name ILIKE :player_name)
    ),
    baseline AS (
        SELECT player_name, encounter_name,
               AVG(parse_percentile) AS baseline_parse,
               AVG(dps) AS baseline_dps,
               AVG(hps) AS baseline_hps
        FROM ranked_fights WHERE rn BETWEEN 3 AND 7
        GROUP BY player_name, encounter_name
        HAVING COUNT(*) >= 3
    ),
    recent AS (
        SELECT player_name, encounter_name,
               AVG(parse_percentile) AS recent_parse,
               AVG(dps) AS recent_dps,
               AVG(hps) AS recent_hps
        FROM ranked_fights WHERE rn BETWEEN 1 AND 2
        GROUP BY player_name, encounter_name
    )
    SELECT r.player_name, r.encounter_name,
           ROUND(r.recent_parse::numeric, 1) AS recent_parse,
           ROUND(b.baseline_parse::numeric, 1) AS baseline_parse,
           ROUND(r.recent_dps::numeric, 1) AS recent_dps,
           ROUND(b.baseline_dps::numeric, 1) AS baseline_dps,
           ROUND(r.recent_hps::numeric, 1) AS recent_hps,
           ROUND(b.baseline_hps::numeric, 1) AS baseline_hps,
           ROUND((r.recent_parse - b.baseline_parse)::numeric, 1) AS parse_delta,
           ROUND(((r.recent_dps - b.baseline_dps)
               / NULLIF(b.baseline_dps, 0) * 100)::numeric, 1) AS dps_delta_pct,
           ROUND(((r.recent_hps - b.baseline_hps)
               / NULLIF(b.baseline_hps, 0) * 100)::numeric, 1) AS hps_delta_pct
    FROM recent r
    JOIN baseline b ON LOWER(r.player_name) = LOWER(b.player_name)
                   AND r.encounter_name = b.encounter_name
    WHERE ABS(r.recent_parse - b.baseline_parse) >= 15
    ORDER BY parse_delta ASC
""")

MY_RECENT_KILLS = text("""
    SELECT f.report_code, f.fight_id, e.name AS encounter_name,
           fp.dps, fp.hps, fp.parse_percentile, fp.deaths, fp.item_level,
           f.duration_ms, r.title AS report_title, r.start_time AS report_time
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    JOIN reports r ON f.report_code = r.code
    WHERE fp.is_my_character = true
      AND f.kill = true
      AND (CAST(:encounter_name AS text) IS NULL OR e.name ILIKE :encounter_name)
    ORDER BY r.start_time DESC, f.fight_id DESC
    LIMIT :limit
""")

