"""Table-data SQL queries for --with-tables agent tools (4 queries).

Used by: agent/tools/table_tools.py, api/routes/data/events.py
"""

from sqlalchemy import text

__all__ = [
    "ABILITY_BREAKDOWN",
    "BUFF_ANALYSIS",
    "OVERHEAL_ANALYSIS",
    "PLAYER_BUFFS_FOR_TRINKETS",
]

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

PLAYER_BUFFS_FOR_TRINKETS = text("""
    SELECT bu.ability_name, bu.spell_id, bu.uptime_pct
    FROM buff_uptimes bu
    JOIN fights f ON bu.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND bu.player_name ILIKE :player_name
      AND bu.metric_type = 'buff'
""")
