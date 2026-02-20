"""Raid-level comparison SQL queries (4 queries).

Used by: agent/tools/raid_tools.py, api/routes/data/reports.py
"""

from sqlalchemy import text

__all__ = [
    "RAID_SUMMARY",
    "RAID_VS_TOP_SPEED",
    "COMPARE_TWO_RAIDS",
    "RAID_EXECUTION_SUMMARY",
]

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

RAID_VS_TOP_SPEED = text("""
    WITH my_raid AS (
        SELECT f.fight_id, f.encounter_id, e.name AS encounter_name,
               f.duration_ms, f.kill,
               COUNT(fp.id) AS player_count,
               SUM(fp.deaths) AS total_deaths,
               SUM(fp.interrupts) AS total_interrupts,
               SUM(fp.dispels) AS total_dispels,
               ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
               ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps
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
           mr.total_deaths, mr.total_interrupts, mr.total_dispels,
           mr.avg_dps, mr.avg_hps,
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
               ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
               STRING_AGG(DISTINCT fp.player_spec || ' ' || fp.player_class, ', '
                   ORDER BY fp.player_spec || ' ' || fp.player_class) AS composition,
               ROW_NUMBER() OVER (
                   PARTITION BY f.encounter_id ORDER BY f.id
               ) AS rn
        FROM fights f
        JOIN encounters e ON f.encounter_id = e.id
        LEFT JOIN fight_performances fp ON fp.fight_id = f.id
        WHERE f.report_code = :report_a
          AND f.kill = true
        GROUP BY f.id, f.encounter_id, e.name, f.duration_ms, f.kill
    ),
    raid_b AS (
        SELECT f.encounter_id, e.name AS encounter_name,
               f.duration_ms, f.kill,
               COUNT(fp.id) AS player_count,
               SUM(fp.deaths) AS total_deaths,
               SUM(fp.interrupts) AS total_interrupts,
               SUM(fp.dispels) AS total_dispels,
               ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
               ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
               STRING_AGG(DISTINCT fp.player_spec || ' ' || fp.player_class, ', '
                   ORDER BY fp.player_spec || ' ' || fp.player_class) AS composition,
               ROW_NUMBER() OVER (
                   PARTITION BY f.encounter_id ORDER BY f.id
               ) AS rn
        FROM fights f
        JOIN encounters e ON f.encounter_id = e.id
        LEFT JOIN fight_performances fp ON fp.fight_id = f.id
        WHERE f.report_code = :report_b
          AND f.kill = true
        GROUP BY f.id, f.encounter_id, e.name, f.duration_ms, f.kill
    )
    SELECT COALESCE(a.encounter_name, b.encounter_name) AS encounter_name,
           a.duration_ms AS a_duration_ms, b.duration_ms AS b_duration_ms,
           a.total_deaths AS a_deaths, b.total_deaths AS b_deaths,
           a.total_interrupts AS a_interrupts, b.total_interrupts AS b_interrupts,
           a.total_dispels AS a_dispels, b.total_dispels AS b_dispels,
           a.avg_dps AS a_avg_dps, b.avg_dps AS b_avg_dps,
           a.avg_hps AS a_avg_hps, b.avg_hps AS b_avg_hps,
           a.player_count AS a_players, b.player_count AS b_players,
           a.composition AS a_comp, b.composition AS b_comp
    FROM raid_a a
    FULL OUTER JOIN raid_b b
        ON a.encounter_id = b.encounter_id AND a.rn = b.rn
    ORDER BY COALESCE(a.encounter_name, b.encounter_name), COALESCE(a.rn, b.rn)
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
           ROUND(AVG(fp.hps)::numeric, 1) AS raid_avg_hps,
           ROUND(SUM(fp.hps)::numeric, 1) AS raid_total_hps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           ROUND(AVG(fp.item_level)::numeric, 1) AS avg_ilvl
    FROM fights f
    JOIN encounters e ON f.encounter_id = e.id
    LEFT JOIN fight_performances fp ON fp.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.kill = true
    GROUP BY e.name, f.fight_id, f.duration_ms
    ORDER BY f.fight_id ASC
    LIMIT 25
""")
