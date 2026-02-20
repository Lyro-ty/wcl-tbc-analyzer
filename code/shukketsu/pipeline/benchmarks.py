"""Benchmark pipeline — discover top reports, ingest, compute aggregates."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from shukketsu.db.models import BenchmarkReport, EncounterBenchmark, WatchedGuild
from shukketsu.db.queries import benchmark as bq
from shukketsu.pipeline.ingest import ingest_report

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    discovered: int = 0
    ingested: int = 0
    computed: int = 0
    errors: list[str] = field(default_factory=list)


async def discover_benchmark_reports(
    session, encounter_id=None, max_per_encounter=10,
) -> list[dict]:
    """Discover report codes from speed rankings and watched guilds.

    Returns a list of dicts: {report_code, source, encounter_id, guild_name}.
    Filters out codes already in benchmark_reports.
    """
    # Query speed ranking report codes
    result = await session.execute(
        bq.SPEED_RANKING_REPORT_CODES,
        {"encounter_id": encounter_id},
    )
    speed_rows = result.fetchall()

    # Deduplicate per encounter, limit to max_per_encounter
    seen_per_encounter: dict[int, int] = {}
    seen_codes: set[str] = set()
    candidates: list[dict] = []
    for row in speed_rows:
        eid = row.encounter_id
        code = row.report_code
        if code in seen_codes:
            logger.debug("Skipping %s (already seen for another encounter)", code)
            continue
        count = seen_per_encounter.get(eid, 0)
        if count >= max_per_encounter:
            continue
        seen_per_encounter[eid] = count + 1
        seen_codes.add(code)
        candidates.append({
            "report_code": code,
            "source": "speed_ranking",
            "encounter_id": eid,
            "guild_name": row.guild_name,
        })

    # Query watched guilds (log for now — TODO: WCL API guild report discovery)
    watched_result = await session.execute(
        select(WatchedGuild).where(WatchedGuild.is_active.is_(True))
    )
    watched_guilds = watched_result.scalars().all()
    for guild in watched_guilds:
        logger.info(
            "Watched guild %s (%s-%s) — guild report discovery not yet implemented",
            guild.guild_name, guild.server_slug, guild.server_region,
        )

    # Filter out already-ingested benchmark codes
    existing_result = await session.execute(bq.EXISTING_BENCHMARK_CODES)
    existing_codes = {row.report_code for row in existing_result.fetchall()}

    new_reports = [
        c for c in candidates if c["report_code"] not in existing_codes
    ]

    logger.info(
        "Discovered %d candidate reports (%d new, %d already ingested)",
        len(candidates), len(new_reports), len(candidates) - len(new_reports),
    )
    return new_reports


async def ingest_benchmark_reports(
    wcl, session, reports: list[dict],
) -> dict:
    """Ingest discovered reports via the standard pipeline.

    Returns {"ingested": N, "errors": N}.
    """
    ingested = 0
    errors = 0
    for report in reports:
        code = report["report_code"]
        try:
            async with session.begin_nested():
                await ingest_report(
                    wcl, session, code,
                    ingest_tables=True,
                    ingest_events=True,
                )
                session.add(BenchmarkReport(
                    report_code=code,
                    source=report["source"],
                    encounter_id=report.get("encounter_id"),
                    guild_name=report.get("guild_name"),
                ))
            await session.commit()
            ingested += 1
            logger.info("Ingested benchmark report %s", code)
        except Exception:
            logger.exception("Failed to ingest benchmark report %s", code)
            await session.rollback()
            errors += 1

    return {"ingested": ingested, "errors": errors}


async def compute_encounter_benchmarks(
    session, encounter_id=None,
) -> dict:
    """Compute aggregate benchmarks from ingested benchmark reports.

    Executes all aggregation queries and merges EncounterBenchmark rows.
    Returns {"computed": N}.
    """
    params = {"encounter_id": encounter_id}

    # Execute all aggregation queries
    kill_result = await session.execute(bq.BENCHMARK_KILL_STATS, params)
    kill_rows = kill_result.fetchall()

    death_result = await session.execute(bq.BENCHMARK_DEATHS, params)
    death_rows = death_result.fetchall()

    spec_dps_result = await session.execute(bq.BENCHMARK_SPEC_DPS, params)
    spec_dps_rows = spec_dps_result.fetchall()

    spec_gcd_result = await session.execute(bq.BENCHMARK_SPEC_GCD, params)
    spec_gcd_rows = spec_gcd_result.fetchall()

    ability_result = await session.execute(bq.BENCHMARK_SPEC_ABILITIES, params)
    ability_rows = ability_result.fetchall()

    buff_result = await session.execute(bq.BENCHMARK_SPEC_BUFFS, params)
    buff_rows = buff_result.fetchall()

    cooldown_result = await session.execute(bq.BENCHMARK_SPEC_COOLDOWNS, params)
    cooldown_rows = cooldown_result.fetchall()

    consumable_result = await session.execute(bq.BENCHMARK_CONSUMABLE_RATES, params)
    consumable_rows = consumable_result.fetchall()

    composition_result = await session.execute(bq.BENCHMARK_COMPOSITION, params)
    composition_rows = composition_result.fetchall()

    # Index supplementary data by (encounter_id, class, spec)
    deaths_by_encounter = {
        row.encounter_id: {
            "avg_deaths": float(row.avg_deaths),
            "zero_death_pct": float(row.zero_death_pct),
        }
        for row in death_rows
    }

    spec_dps_index: dict[tuple, dict] = {}
    for row in spec_dps_rows:
        key = (row.encounter_id, row.player_class, row.player_spec)
        spec_dps_index[key] = {
            "sample_size": row.sample_size,
            "avg_dps": float(row.avg_dps),
            "median_dps": float(row.median_dps),
            "p75_dps": float(row.p75_dps),
            "avg_hps": float(row.avg_hps),
            "median_hps": float(row.median_hps),
            "p75_hps": float(row.p75_hps),
        }

    spec_gcd_index: dict[tuple, dict] = {}
    for row in spec_gcd_rows:
        key = (row.encounter_id, row.player_class, row.player_spec)
        spec_gcd_index[key] = {
            "avg_gcd_uptime": float(row.avg_gcd_uptime),
            "avg_cpm": float(row.avg_cpm),
        }

    ability_index: dict[tuple, list] = {}
    for row in ability_rows:
        key = (row.encounter_id, row.player_class, row.player_spec)
        ability_index.setdefault(key, []).append({
            "ability_name": row.ability_name,
            "avg_damage_pct": float(row.avg_damage_pct),
        })

    buff_index: dict[tuple, list] = {}
    for row in buff_rows:
        key = (row.encounter_id, row.player_class, row.player_spec)
        buff_index.setdefault(key, []).append({
            "buff_name": row.buff_name,
            "avg_uptime": float(row.avg_uptime),
        })

    cooldown_index: dict[tuple, list] = {}
    for row in cooldown_rows:
        key = (row.encounter_id, row.player_class, row.player_spec)
        cooldown_index.setdefault(key, []).append({
            "ability_name": row.ability_name,
            "avg_uses": float(row.avg_uses),
            "avg_efficiency": float(row.avg_efficiency),
        })

    consumables = [
        {
            "category": row.category,
            "usage_pct": float(row.usage_pct),
            "players_with": row.players_with,
            "total_player_fights": row.total_player_fights,
        }
        for row in consumable_rows
    ]

    composition_index: dict[int, list] = {}
    for row in composition_rows:
        composition_index.setdefault(row.encounter_id, []).append({
            "class": row.player_class,
            "spec": row.player_spec,
            "avg_count": float(row.avg_count),
        })

    # Build benchmarks dict per encounter
    computed = 0
    # Collect all spec keys across encounters for by_spec
    all_spec_keys: dict[int, set] = {}
    for key in spec_dps_index:
        all_spec_keys.setdefault(key[0], set()).add((key[1], key[2]))
    for key in spec_gcd_index:
        all_spec_keys.setdefault(key[0], set()).add((key[1], key[2]))

    for kill_row in kill_rows:
        eid = kill_row.encounter_id
        benchmarks: dict = {
            "kill_stats": {
                "kill_count": kill_row.kill_count,
                "avg_duration_ms": float(kill_row.avg_duration_ms),
                "median_duration_ms": float(kill_row.median_duration_ms),
                "min_duration_ms": kill_row.min_duration_ms,
            },
            "deaths": deaths_by_encounter.get(eid, {}),
            "by_spec": {},
            "consumables": consumables,
            "composition": composition_index.get(eid, []),
        }

        # Populate per-spec data
        spec_keys = all_spec_keys.get(eid, set())
        for cls, spec in sorted(spec_keys):
            spec_key = (eid, cls, spec)
            label = f"{spec} {cls}"
            benchmarks["by_spec"][label] = {
                "dps": spec_dps_index.get(spec_key, {}),
                "gcd": spec_gcd_index.get(spec_key, {}),
                "abilities": ability_index.get(spec_key, []),
                "buffs": buff_index.get(spec_key, []),
                "cooldowns": cooldown_index.get(spec_key, []),
            }

        await session.merge(EncounterBenchmark(
            encounter_id=eid,
            sample_size=kill_row.kill_count,
            # Strip tzinfo: column is TIMESTAMP WITHOUT TIME ZONE
            computed_at=datetime.now(UTC).replace(tzinfo=None),
            benchmarks=benchmarks,
        ))
        computed += 1

    await session.commit()
    logger.info("Computed benchmarks for %d encounters", computed)
    return {"computed": computed}


async def run_benchmark_pipeline(
    wcl, session, encounter_id=None, max_reports_per_encounter=10,
    *, compute_only=False, force=False,
) -> BenchmarkResult:
    """Orchestrate the full benchmark pipeline: discover -> ingest -> compute.

    Args:
        wcl: WCL API client.
        session: Async database session.
        encounter_id: Optional filter for a single encounter.
        max_reports_per_encounter: Max reports to discover per encounter.
        compute_only: Skip discover+ingest, only run compute.
        force: Ignored for now (reserved for forced re-ingestion).
    """
    result = BenchmarkResult()

    if not compute_only:
        # Discover
        reports = await discover_benchmark_reports(
            session, encounter_id=encounter_id,
            max_per_encounter=max_reports_per_encounter,
        )
        result.discovered = len(reports)

        # Ingest
        if reports:
            ingest_result = await ingest_benchmark_reports(wcl, session, reports)
            result.ingested = ingest_result["ingested"]
            if ingest_result["errors"]:
                result.errors.append(
                    f"{ingest_result['errors']} reports failed to ingest"
                )

    # Compute
    compute_result = await compute_encounter_benchmarks(
        session, encounter_id=encounter_id,
    )
    result.computed = compute_result["computed"]

    logger.info(
        "Benchmark pipeline complete: %d discovered, %d ingested, "
        "%d computed, %d errors",
        result.discovered, result.ingested, result.computed, len(result.errors),
    )
    return result
