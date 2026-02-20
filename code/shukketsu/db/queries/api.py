"""REST API-only SQL queries (19 queries).

Used by: api/routes/data/reports.py, api/routes/data/fights.py,
         api/routes/data/characters.py, api/routes/data/rankings.py
"""

from sqlalchemy import text

__all__ = [
    "REPORTS_LIST",
    "ENCOUNTERS_LIST",
    "CHARACTERS_LIST",
    "CHARACTER_REPORTS",
    "REPORT_DEATHS",
    "RAID_ABILITY_SUMMARY",
    "FIGHT_ABILITIES",
    "FIGHT_ABILITIES_PLAYER",
    "FIGHT_BUFFS",
    "FIGHT_BUFFS_PLAYER",
    "TABLE_DATA_EXISTS",
    "EVENT_DATA_EXISTS",
    "CHARACTER_PROFILE",
    "CHARACTER_RECENT_PARSES",
    "DASHBOARD_STATS",
    "RECENT_REPORTS",
    "CHARACTER_REPORT_DETAIL",
    "FIGHT_DEATHS",
    "GEAR_SNAPSHOT",
]

REPORTS_LIST = text("""
    SELECT r.code, r.title, r.guild_name, r.start_time, r.end_time,
           COUNT(DISTINCT f.id) AS fight_count,
           COUNT(DISTINCT f.encounter_id) AS boss_count
    FROM reports r
    LEFT JOIN fights f ON f.report_code = r.code
    GROUP BY r.code, r.title, r.guild_name, r.start_time, r.end_time
    ORDER BY r.start_time DESC
    LIMIT 200
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
           ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           SUM(fp.deaths) AS total_deaths
    FROM reports r
    JOIN fights f ON r.code = f.report_code
    JOIN fight_performances fp ON f.id = fp.fight_id
    WHERE fp.player_name ILIKE :character_name
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
      AND am.player_name ILIKE :player_name
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
      AND bu.player_name ILIKE :player_name
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
    SELECT (
        EXISTS(
            SELECT 1 FROM death_details dd
            JOIN fights f ON dd.fight_id = f.id
            WHERE f.report_code = :report_code
        ) OR EXISTS(
            SELECT 1 FROM cast_metrics cm
            JOIN fights f ON cm.fight_id = f.id
            WHERE f.report_code = :report_code
        ) OR EXISTS(
            SELECT 1 FROM resource_snapshots rs
            JOIN fights f ON rs.fight_id = f.id
            WHERE f.report_code = :report_code
        )
    ) AS has_data
""")

CHARACTER_PROFILE = text("""
    SELECT mc.id, mc.name, mc.server_slug, mc.server_region,
           mc.character_class, mc.spec,
           COUNT(fp.id) AS total_fights,
           SUM(CASE WHEN f.kill THEN 1 ELSE 0 END) AS total_kills,
           COALESCE(SUM(fp.deaths), 0) AS total_deaths,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(MAX(fp.dps)::numeric, 1) AS best_dps,
           ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
           ROUND(MAX(fp.hps)::numeric, 1) AS best_hps,
           ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse,
           ROUND(MAX(fp.parse_percentile)::numeric, 1) AS best_parse,
           ROUND(AVG(fp.item_level)::numeric, 1) AS avg_ilvl
    FROM my_characters mc
    LEFT JOIN fight_performances fp ON LOWER(fp.player_name) = LOWER(mc.name)
    LEFT JOIN fights f ON fp.fight_id = f.id
    WHERE mc.name ILIKE :character_name
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
    JOIN my_characters mc ON LOWER(mc.name) = LOWER(fp.player_name)
    WHERE mc.name ILIKE :character_name
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
           ROUND(AVG(fp.dps) FILTER (WHERE f.kill)::numeric, 1) AS avg_kill_dps,
           ROUND(AVG(fp.hps) FILTER (WHERE f.kill)::numeric, 1) AS avg_kill_hps
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
      AND fp.player_name ILIKE :character_name
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

GEAR_SNAPSHOT = text("""
    SELECT gs.slot, gs.item_id, gs.item_level, gs.player_name
    FROM gear_snapshots gs
    JOIN fights f ON gs.fight_id = f.id
    WHERE f.report_code = :report_code AND f.fight_id = :fight_id
      AND gs.player_name ILIKE :player_name
    ORDER BY gs.slot
""")
