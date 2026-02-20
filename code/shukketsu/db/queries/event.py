"""Event-data SQL queries for --with-events agent tools (16 queries).

Used by: agent/tools/event_tools.py, api/routes/data/events.py,
         api/routes/data/fights.py, api/routes/data/comparison.py
"""

from sqlalchemy import text

__all__ = [
    "DEATH_ANALYSIS",
    "CAST_ACTIVITY",
    "COOLDOWN_EFFICIENCY",
    "CANCELLED_CASTS",
    "CONSUMABLE_CHECK",
    "RESOURCE_USAGE",
    "GEAR_CHANGES",
    "PHASE_BREAKDOWN",
    "FIGHT_CAST_METRICS",
    "FIGHT_COOLDOWNS",
    "CAST_TIMELINE",
    "COOLDOWN_WINDOWS",
    "CAST_EVENTS_FOR_DOT_ANALYSIS",
    "PLAYER_FIGHT_INFO",
    "CAST_EVENTS_FOR_PHASES",
    "ENCHANT_GEM_CHECK",
]

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
      AND (CAST(:player_name AS text) IS NULL OR dd.player_name ILIKE :player_name)
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
      AND (CAST(:player_name AS text) IS NULL OR cm.player_name ILIKE :player_name)
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
      AND (CAST(:player_name AS text) IS NULL OR cu.player_name ILIKE :player_name)
    ORDER BY cu.player_name, cu.efficiency_pct ASC
""")

CANCELLED_CASTS = text("""
    SELECT cc.player_name, cc.total_begins, cc.total_completions,
           cc.cancel_count, cc.cancel_pct, cc.top_cancelled_json
    FROM cancelled_casts cc
    JOIN fights f ON cc.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cc.player_name ILIKE :player_name
""")

CONSUMABLE_CHECK = text("""
    SELECT fc.player_name, fc.category, fc.ability_name, fc.spell_id, fc.active
    FROM fight_consumables fc
    JOIN fights f ON fc.fight_id = f.id
    WHERE f.report_code = :report_code AND f.fight_id = :fight_id
      AND (CAST(:player_name AS text) IS NULL OR fc.player_name ILIKE :player_name)
    ORDER BY fc.player_name, fc.category
""")

RESOURCE_USAGE = text("""
    SELECT rs.player_name, rs.resource_type,
           rs.min_value, rs.max_value, rs.avg_value,
           rs.time_at_zero_ms, rs.time_at_zero_pct,
           rs.samples_json
    FROM resource_snapshots rs
    JOIN fights f ON rs.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND rs.player_name ILIKE :player_name
""")

GEAR_CHANGES = text("""
    WITH old_gear AS (
        SELECT gs.slot, gs.item_id, gs.item_level
        FROM gear_snapshots gs
        JOIN fights f ON gs.fight_id = f.id
        WHERE f.report_code = :report_code_old
          AND gs.player_name ILIKE :player_name
          AND f.id = (
              SELECT MIN(f2.id) FROM fights f2
              WHERE f2.report_code = :report_code_old
          )
    ),
    new_gear AS (
        SELECT gs.slot, gs.item_id, gs.item_level
        FROM gear_snapshots gs
        JOIN fights f ON gs.fight_id = f.id
        WHERE f.report_code = :report_code_new
          AND gs.player_name ILIKE :player_name
          AND f.id = (
              SELECT MIN(f2.id) FROM fights f2
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

PHASE_BREAKDOWN = text("""
    SELECT f.report_code, f.fight_id, f.duration_ms, f.kill,
           e.name AS encounter_name,
           fp.player_name, fp.player_class, fp.player_spec,
           fp.dps, fp.total_damage, fp.hps, fp.total_healing,
           fp.deaths, fp.parse_percentile
    FROM fights f
    JOIN encounters e ON f.encounter_id = e.id
    JOIN fight_performances fp ON fp.fight_id = f.id
    WHERE f.report_code = :report_code AND f.fight_id = :fight_id
      AND (CAST(:player_name AS text) IS NULL OR fp.player_name ILIKE :player_name)
    ORDER BY fp.dps DESC
""")

FIGHT_CAST_METRICS = text("""
    SELECT cm.player_name, cm.total_casts, cm.casts_per_minute,
           cm.gcd_uptime_pct, cm.active_time_ms, cm.downtime_ms,
           cm.longest_gap_ms, cm.longest_gap_at_ms, cm.avg_gap_ms, cm.gap_count
    FROM cast_metrics cm
    JOIN fights f ON cm.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cm.player_name ILIKE :player_name
""")

FIGHT_COOLDOWNS = text("""
    SELECT cu.player_name, cu.ability_name, cu.spell_id, cu.cooldown_sec,
           cu.times_used, cu.max_possible_uses, cu.first_use_ms, cu.last_use_ms,
           cu.efficiency_pct
    FROM cooldown_usage cu
    JOIN fights f ON cu.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cu.player_name ILIKE :player_name
    ORDER BY cu.efficiency_pct ASC
""")

CAST_TIMELINE = text("""
    SELECT ce.player_name, ce.timestamp_ms, ce.spell_id,
           ce.ability_name, ce.event_type, ce.target_name
    FROM cast_events ce
    JOIN fights f ON ce.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND ce.player_name ILIKE :player_name
    ORDER BY ce.timestamp_ms ASC
""")

COOLDOWN_WINDOWS = text("""
    SELECT cu.player_name, cu.ability_name, cu.spell_id,
           cu.cooldown_sec, cu.times_used, cu.max_possible_uses,
           cu.first_use_ms, cu.last_use_ms, cu.efficiency_pct,
           fp.dps AS baseline_dps, fp.total_damage,
           (f.end_time - f.start_time) AS fight_duration_ms
    FROM cooldown_usage cu
    JOIN fights f ON cu.fight_id = f.id
    JOIN fight_performances fp
        ON fp.fight_id = f.id AND LOWER(fp.player_name) = LOWER(cu.player_name)
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND cu.player_name ILIKE :player_name
      AND cu.times_used > 0
    ORDER BY cu.first_use_ms ASC NULLS LAST
""")

CAST_EVENTS_FOR_DOT_ANALYSIS = text("""
    SELECT ce.spell_id, ce.ability_name, ce.timestamp_ms, ce.event_type
    FROM cast_events ce
    JOIN fights f ON ce.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND ce.player_name ILIKE :player_name
      AND ce.event_type = 'cast'
    ORDER BY ce.spell_id, ce.timestamp_ms ASC
""")

PLAYER_FIGHT_INFO = text("""
    SELECT fp.player_class, fp.player_spec, fp.dps, fp.total_damage,
           (f.end_time - f.start_time) AS fight_duration_ms,
           f.encounter_id, e.name AS encounter_name
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND fp.player_name ILIKE :player_name
""")

CAST_EVENTS_FOR_PHASES = text("""
    SELECT ce.timestamp_ms, ce.event_type
    FROM cast_events ce
    JOIN fights f ON ce.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND ce.player_name ILIKE :player_name
      AND ce.event_type = 'cast'
    ORDER BY ce.timestamp_ms ASC
""")

ENCHANT_GEM_CHECK = text("""
    SELECT gs.player_name, gs.slot, gs.item_id, gs.item_level,
           gs.permanent_enchant, gs.temporary_enchant, gs.gems_json
    FROM gear_snapshots gs
    JOIN fights f ON gs.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND gs.player_name ILIKE :player_name
    ORDER BY gs.slot ASC
""")
