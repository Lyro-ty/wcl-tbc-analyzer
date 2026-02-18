"""Pipeline for ingesting WCL table data (ability breakdowns, buff uptimes)."""

import json
import logging
from typing import Any

from sqlalchemy import delete, select

from shukketsu.db.models import AbilityMetric, BuffUptime, Fight

logger = logging.getLogger(__name__)


def parse_table_response(raw: Any) -> list[dict]:
    """Parse WCL table response, handling JSON string/dict ambiguity."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        return raw.get("entries", [])
    if isinstance(raw, list):
        return raw
    return []


def parse_ability_metrics(
    entries: list[dict],
    fight_id: int,
    player_name: str,
    metric_type: str,
) -> list[AbilityMetric]:
    """Parse ability entries into AbilityMetric rows. Takes top 20 by total."""
    sorted_entries = sorted(entries, key=lambda e: e.get("total", 0), reverse=True)
    player_total = sum(e.get("total", 0) for e in sorted_entries)

    result = []
    for entry in sorted_entries[:20]:
        total = entry.get("total", 0)
        pct = (total / player_total * 100) if player_total > 0 else 0.0
        hit_count = entry.get("hitCount", entry.get("uses", 0)) or 0
        crit_count = entry.get("critCount", 0) or 0
        # Some entries report hitdetails instead of top-level crit
        crit_pct = 0.0
        if hit_count > 0 and crit_count > 0:
            crit_pct = crit_count / hit_count * 100
        # WCL sometimes provides a direct critPct field — prefer it if available
        if "critPct" in entry and entry["critPct"]:
            crit_pct = entry["critPct"]

        overheal = None
        if metric_type == "healing":
            overheal = entry.get("overheal", entry.get("totalOverheal")) or None
            if overheal is not None:
                overheal = int(overheal)

        result.append(AbilityMetric(
            fight_id=fight_id,
            player_name=player_name,
            metric_type=metric_type,
            ability_name=entry.get("name", "Unknown"),
            spell_id=entry.get("guid", entry.get("id", 0)),
            total=total,
            hit_count=hit_count,
            crit_count=crit_count,
            crit_pct=round(crit_pct, 1),
            pct_of_total=round(pct, 1),
            overheal_total=overheal,
        ))
    return result


def parse_buff_uptimes(
    entries: list[dict],
    fight_id: int,
    player_name: str,
    metric_type: str,
    fight_duration_ms: int,
) -> list[BuffUptime]:
    """Parse buff/debuff entries into BuffUptime rows. Takes top 30 by uptime."""
    result = []
    for entry in entries:
        uptime_ms = entry.get("uptime", 0) or 0
        uptime_pct = (uptime_ms / fight_duration_ms * 100) if fight_duration_ms > 0 else 0.0
        # Some entries already provide totalUptime as percentage
        if uptime_pct > 100:
            uptime_pct = 100.0

        result.append({
            "entry": entry,
            "uptime_pct": uptime_pct,
        })

    # Sort by uptime descending, take top 30
    result.sort(key=lambda x: x["uptime_pct"], reverse=True)

    rows = []
    for item in result[:30]:
        entry = item["entry"]
        rows.append(BuffUptime(
            fight_id=fight_id,
            player_name=player_name,
            metric_type=metric_type,
            ability_name=entry.get("name", "Unknown"),
            spell_id=entry.get("guid", entry.get("id", 0)),
            uptime_pct=round(item["uptime_pct"], 1),
            stack_count=entry.get("totalUseCount", 0) or 0,
        ))
    return rows


async def ingest_table_data_for_fight(
    wcl, session, report_code: str, fight: Fight,
) -> int:
    """Fetch and ingest table data for a single fight. Returns count of rows inserted."""
    from shukketsu.wcl.queries import REPORT_TABLE

    rate_limit_frag = "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"
    query = REPORT_TABLE.replace("RATE_LIMIT", rate_limit_frag)
    fight_duration_ms = fight.end_time - fight.start_time

    total_rows = 0

    # Fetch 4 data types: DamageDone, Healing, Buffs, Debuffs
    data_type_config = [
        ("DamageDone", "damage", "ability"),
        ("Healing", "healing", "ability"),
        ("Buffs", "buff", "buff"),
        ("Debuffs", "debuff", "buff"),
    ]

    for wcl_type, metric_type, parse_kind in data_type_config:
        try:
            raw_data = await wcl.query(
                query,
                variables={
                    "code": report_code,
                    "fightIDs": [fight.fight_id],
                    "dataType": wcl_type,
                },
            )
            table_raw = raw_data["reportData"]["report"]["table"]
            top_entries = parse_table_response(table_raw)

            # Delete only THIS type's rows right before insert (prevents
            # partial data loss if a later API call fails)
            if parse_kind == "ability":
                await session.execute(
                    delete(AbilityMetric).where(
                        AbilityMetric.fight_id == fight.id,
                        AbilityMetric.metric_type == metric_type,
                    )
                )
            else:
                await session.execute(
                    delete(BuffUptime).where(
                        BuffUptime.fight_id == fight.id,
                        BuffUptime.metric_type == metric_type,
                    )
                )

            # Without sourceID, WCL returns entries grouped by source (player)
            for source_entry in top_entries:
                player_name = source_entry.get("name", "")
                if not player_name:
                    continue

                sub_entries = source_entry.get("entries", [])
                if not sub_entries:
                    # Flat format (single-source or unexpected shape) — skip
                    continue

                if parse_kind == "ability":
                    metrics = parse_ability_metrics(
                        sub_entries, fight.id, player_name, metric_type,
                    )
                    for m in metrics:
                        session.add(m)
                    total_rows += len(metrics)
                else:
                    uptimes = parse_buff_uptimes(
                        sub_entries, fight.id, player_name, metric_type,
                        fight_duration_ms,
                    )
                    for u in uptimes:
                        session.add(u)
                    total_rows += len(uptimes)

        except Exception:
            logger.exception(
                "Failed to fetch %s table data for fight %d in %s",
                wcl_type, fight.fight_id, report_code,
            )
            continue

    logger.info(
        "Ingested table data for fight %d (%s): %d rows",
        fight.fight_id, report_code, total_rows,
    )
    return total_rows


async def ingest_table_data_for_report(
    wcl, session, report_code: str,
) -> int:
    """Ingest table data for all fights in a report. Returns total rows inserted."""
    fights = await session.execute(
        select(Fight).where(Fight.report_code == report_code)
    )
    fight_list = list(fights.scalars().all())

    if not fight_list:
        logger.warning("No fights found for report %s", report_code)
        return 0

    total_rows = 0
    for fight in fight_list:
        rows = await ingest_table_data_for_fight(
            wcl, session, report_code, fight,
        )
        total_rows += rows

    logger.info(
        "Ingested table data for report %s: %d total rows across %d fights",
        report_code, total_rows, len(fight_list),
    )
    return total_rows
