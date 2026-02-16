"""Top rankings ingestion pipeline.

Fetches characterRankings from the WCL API for each encounter x class/spec combo
and persists them to the top_rankings table.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from shukketsu.db.models import TopRanking

logger = logging.getLogger(__name__)

MAX_RANKINGS = 50


def parse_zone_rankings(
    raw_data,
    encounter_id: int,
    class_name: str,
    spec_name: str,
    metric: str,
) -> list[TopRanking]:
    """Parse WCL characterRankings JSON into TopRanking ORM objects.

    raw_data: The characterRankings value from the WCL response.
    Could be a dict or a JSON string (WCL returns it as a JSON scalar).
    """
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)

    if raw_data is None:
        return []

    rankings_list = raw_data.get("rankings", [])
    result = []

    for i, entry in enumerate(rankings_list[:MAX_RANKINGS], start=1):
        server = entry.get("server") or {}
        guild = entry.get("guild") or {}

        result.append(
            TopRanking(
                encounter_id=encounter_id,
                class_=class_name,
                spec=spec_name,
                metric=metric,
                rank_position=i,
                player_name=entry["name"],
                player_server=server.get("name", ""),
                amount=entry.get("amount", 0.0),
                duration_ms=entry.get("duration", 0),
                report_code=entry.get("reportCode", ""),
                fight_id=entry.get("fightID", 0),
                guild_name=guild.get("name"),
                item_level=entry.get("bracketData"),
            )
        )

    return result


@dataclass
class RankingsResult:
    """Aggregated result from a rankings ingestion run."""

    fetched: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


async def fetch_rankings_for_spec(
    wcl,
    session,
    encounter_id: int,
    class_name: str,
    spec_name: str,
    metric: str = "dps",
) -> int:
    """Fetch rankings for one encounter/class/spec combo.

    Deletes existing rows for this combo, inserts fresh data.
    Returns count of rankings inserted.
    """
    from shukketsu.wcl.queries import ZONE_RANKINGS

    data = await wcl.query(
        ZONE_RANKINGS.replace(
            "RATE_LIMIT",
            "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }",
        ),
        variables={
            "encounterID": encounter_id,
            "className": class_name,
            "specName": spec_name,
            "metric": metric,
            "page": 1,
        },
    )

    raw_rankings = data["worldData"]["encounter"]["characterRankings"]
    rankings = parse_zone_rankings(
        raw_rankings, encounter_id, class_name, spec_name, metric
    )

    # Delete existing rows for this combo
    await session.execute(
        delete(TopRanking).where(
            TopRanking.encounter_id == encounter_id,
            TopRanking.class_ == class_name,
            TopRanking.spec == spec_name,
            TopRanking.metric == metric,
        )
    )

    for r in rankings:
        session.add(r)

    return len(rankings)


async def ingest_all_rankings(
    wcl,
    session,
    encounter_ids: list[int],
    specs: list,  # list of ClassSpec or similar with .class_name, .spec_name, .role
    include_hps: bool = False,
    force: bool = False,
    stale_hours: int = 24,
) -> RankingsResult:
    """Fetch top rankings for all encounter x spec combos.

    Commits after each encounter batch. Skips recently-fetched combos
    unless force=True.
    """
    result = RankingsResult()
    total_combos = len(encounter_ids) * len(specs)
    progress = 0

    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    for enc_id in encounter_ids:
        for spec in specs:
            progress += 1
            metrics = ["dps"]
            if include_hps and spec.role == "healer":
                metrics.append("hps")

            for metric in metrics:
                try:
                    # Check staleness (unless force)
                    if not force:
                        existing = await session.execute(
                            select(func.max(TopRanking.fetched_at)).where(
                                TopRanking.encounter_id == enc_id,
                                TopRanking.class_ == spec.class_name,
                                TopRanking.spec == spec.spec_name,
                                TopRanking.metric == metric,
                            )
                        )
                        last_fetched = existing.scalar_one_or_none()
                        if last_fetched and last_fetched.replace(
                            tzinfo=UTC
                        ) > cutoff:
                            result.skipped += 1
                            logger.debug(
                                "[%d/%d] Skipping %s %s on %d (%s) — fresh",
                                progress,
                                total_combos,
                                spec.class_name,
                                spec.spec_name,
                                enc_id,
                                metric,
                            )
                            continue

                    count = await fetch_rankings_for_spec(
                        wcl,
                        session,
                        enc_id,
                        spec.class_name,
                        spec.spec_name,
                        metric,
                    )
                    result.fetched += 1
                    logger.info(
                        "[%d/%d] Fetched %d rankings: %s %s on %d (%s)",
                        progress,
                        total_combos,
                        count,
                        spec.class_name,
                        spec.spec_name,
                        enc_id,
                        metric,
                    )
                except Exception as e:
                    error_msg = (
                        f"{spec.class_name} {spec.spec_name} on {enc_id} ({metric}): {e}"
                    )
                    result.errors.append(error_msg)
                    logger.error(
                        "[%d/%d] Error: %s", progress, total_combos, error_msg
                    )

        # Commit after each encounter batch
        await session.commit()

    return result
