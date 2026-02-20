"""Benchmark SQL queries for discovery, aggregation, and retrieval (11 queries).

Used by: pipeline/benchmarks.py, agent/tools (future), api/routes (future)
"""

from sqlalchemy import text

__all__ = [
    "SPEED_RANKING_REPORT_CODES",
    "EXISTING_BENCHMARK_CODES",
    "BENCHMARK_KILL_STATS",
    "BENCHMARK_DEATHS",
    "BENCHMARK_SPEC_DPS",
    "BENCHMARK_SPEC_GCD",
    "BENCHMARK_SPEC_ABILITIES",
    "BENCHMARK_SPEC_BUFFS",
    "BENCHMARK_SPEC_COOLDOWNS",
    "BENCHMARK_CONSUMABLE_RATES",
    "BENCHMARK_COMPOSITION",
    "GET_ENCOUNTER_BENCHMARK",
]

# -- Discovery queries --

SPEED_RANKING_REPORT_CODES = text("""
    SELECT DISTINCT sr.report_code, sr.encounter_id, sr.guild_name
    FROM speed_rankings sr
    WHERE (CAST(:encounter_id AS integer) IS NULL OR sr.encounter_id = :encounter_id)
    ORDER BY sr.encounter_id, sr.report_code
""")

EXISTING_BENCHMARK_CODES = text("""
    SELECT report_code FROM benchmark_reports
""")

# -- Aggregation queries (all scoped via JOIN to benchmark_reports) --

BENCHMARK_KILL_STATS = text("""
    SELECT f.encounter_id,
           COUNT(*) AS kill_count,
           ROUND(AVG(f.duration_ms)::numeric, 0) AS avg_duration_ms,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP
               (ORDER BY f.duration_ms)::numeric, 0) AS median_duration_ms,
           MIN(f.duration_ms) AS min_duration_ms
    FROM fights f
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id
""")

BENCHMARK_DEATHS = text("""
    SELECT f.encounter_id,
           ROUND(AVG(fp.deaths)::numeric, 2) AS avg_deaths,
           ROUND(
               COUNT(*) FILTER (WHERE fp.deaths = 0)::numeric
               / NULLIF(COUNT(*)::numeric, 0) * 100, 1
           ) AS zero_death_pct
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id
""")

BENCHMARK_SPEC_DPS = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           COUNT(*) AS sample_size,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP
               (ORDER BY fp.dps)::numeric, 1) AS median_dps,
           ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP
               (ORDER BY fp.dps)::numeric, 1) AS p75_dps,
           ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP
               (ORDER BY fp.hps)::numeric, 1) AS median_hps,
           ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP
               (ORDER BY fp.hps)::numeric, 1) AS p75_hps
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec
    HAVING COUNT(*) >= 2
""")

BENCHMARK_SPEC_GCD = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           ROUND(AVG(cm.gcd_uptime_pct)::numeric, 1) AS avg_gcd_uptime,
           ROUND(AVG(cm.casts_per_minute)::numeric, 1) AS avg_cpm
    FROM cast_metrics cm
    JOIN fights f ON cm.fight_id = f.id
    JOIN fight_performances fp
        ON fp.fight_id = f.id AND fp.player_name = cm.player_name
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec
""")

BENCHMARK_SPEC_ABILITIES = text("""
    WITH fight_totals AS (
        SELECT am.fight_id, am.player_name,
               SUM(am.total) AS player_total
        FROM ability_metrics am
        JOIN fights f ON am.fight_id = f.id
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE f.kill = true
          AND am.metric_type = 'damage'
          AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
        GROUP BY am.fight_id, am.player_name
    )
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           am.ability_name,
           ROUND(AVG(
               CASE WHEN ft.player_total > 0
                    THEN am.total::numeric / ft.player_total * 100
                    ELSE 0 END
           )::numeric, 1) AS avg_damage_pct
    FROM ability_metrics am
    JOIN fights f ON am.fight_id = f.id
    JOIN fight_performances fp
        ON fp.fight_id = f.id AND fp.player_name = am.player_name
    JOIN benchmark_reports br ON br.report_code = f.report_code
    JOIN fight_totals ft
        ON ft.fight_id = am.fight_id AND ft.player_name = am.player_name
    WHERE f.kill = true
      AND am.metric_type = 'damage'
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec, am.ability_name
    HAVING ROUND(AVG(
        CASE WHEN ft.player_total > 0
             THEN am.total::numeric / ft.player_total * 100
             ELSE 0 END
    )::numeric, 1) >= 3
    ORDER BY f.encounter_id, fp.player_class, fp.player_spec, avg_damage_pct DESC
""")

BENCHMARK_SPEC_BUFFS = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           bu.ability_name AS buff_name,
           ROUND(AVG(bu.uptime_pct)::numeric, 1) AS avg_uptime
    FROM buff_uptimes bu
    JOIN fights f ON bu.fight_id = f.id
    JOIN fight_performances fp
        ON fp.fight_id = f.id AND fp.player_name = bu.player_name
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec, bu.ability_name
    HAVING ROUND(AVG(bu.uptime_pct)::numeric, 1) >= 20
    ORDER BY f.encounter_id, fp.player_class, fp.player_spec, avg_uptime DESC
""")

BENCHMARK_SPEC_COOLDOWNS = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           cu.ability_name,
           ROUND(AVG(cu.times_used)::numeric, 1) AS avg_uses,
           ROUND(AVG(cu.efficiency_pct)::numeric, 1) AS avg_efficiency
    FROM cooldown_usage cu
    JOIN fights f ON cu.fight_id = f.id
    JOIN fight_performances fp
        ON fp.fight_id = f.id AND fp.player_name = cu.player_name
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec, cu.ability_name
    ORDER BY f.encounter_id, fp.player_class, fp.player_spec, avg_efficiency DESC
""")

BENCHMARK_CONSUMABLE_RATES = text("""
    WITH player_fights AS (
        SELECT DISTINCT f.id AS fight_id, fp.player_name
        FROM fight_performances fp
        JOIN fights f ON fp.fight_id = f.id
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE f.kill = true
          AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
    ),
    consumable_counts AS (
        SELECT fc.category,
               COUNT(DISTINCT (pf.fight_id, pf.player_name)) AS players_with
        FROM fight_consumables fc
        JOIN fights f ON fc.fight_id = f.id
        JOIN player_fights pf
            ON pf.fight_id = f.id AND pf.player_name = fc.player_name
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
        GROUP BY fc.category
    )
    SELECT cc.category,
           cc.players_with,
           (SELECT COUNT(DISTINCT (fight_id, player_name))
            FROM player_fights) AS total_player_fights,
           ROUND(
               cc.players_with::numeric
               / NULLIF(
                   (SELECT COUNT(DISTINCT (fight_id, player_name))
                    FROM player_fights)::numeric, 0
               ) * 100, 1
           ) AS usage_pct
    FROM consumable_counts cc
    ORDER BY usage_pct DESC
""")

BENCHMARK_COMPOSITION = text("""
    WITH per_fight_counts AS (
        SELECT f.encounter_id,
               fp.player_class, fp.player_spec,
               f.id AS fight_id,
               COUNT(*) AS spec_count
        FROM fight_performances fp
        JOIN fights f ON fp.fight_id = f.id
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE f.kill = true
          AND (CAST(:encounter_id AS integer) IS NULL OR f.encounter_id = :encounter_id)
        GROUP BY f.encounter_id, fp.player_class, fp.player_spec, f.id
    )
    SELECT encounter_id, player_class, player_spec,
           ROUND(AVG(spec_count)::numeric, 1) AS avg_count
    FROM per_fight_counts
    GROUP BY encounter_id, player_class, player_spec
    ORDER BY encounter_id, avg_count DESC
""")

# -- Read query --

GET_ENCOUNTER_BENCHMARK = text("""
    SELECT eb.encounter_id, eb.sample_size, eb.computed_at, eb.benchmarks,
           e.name AS encounter_name
    FROM encounter_benchmarks eb
    JOIN encounters e ON eb.encounter_id = e.id
    WHERE e.name ILIKE :encounter_name
""")
