import logging
from dataclasses import dataclass
from typing import Any

from shukketsu.db.models import Fight, FightPerformance, Report
from shukketsu.pipeline.normalize import is_boss_fight

logger = logging.getLogger(__name__)


def parse_report(data: dict[str, Any], code: str) -> Report:
    guild = data.get("guild")
    return Report(
        code=code,
        title=data["title"],
        guild_name=guild["name"] if guild else None,
        guild_id=guild["id"] if guild else None,
        start_time=data["startTime"],
        end_time=data["endTime"],
    )


def parse_fights(fights_data: list[dict[str, Any]], report_code: str) -> list[Fight]:
    result = []
    for f in fights_data:
        if not is_boss_fight(f):
            continue
        result.append(Fight(
            report_code=report_code,
            fight_id=f["id"],
            encounter_id=f["encounterID"],
            start_time=f["startTime"],
            end_time=f["endTime"],
            kill=f["kill"],
            difficulty=f.get("difficulty", 0),
        ))
    return result


def parse_rankings_to_performances(
    rankings_data: list[dict[str, Any]],
    fight_id: int,
    my_character_names: set[str],
) -> list[FightPerformance]:
    result = []
    for r in rankings_data:
        server = r.get("server", {})
        server_name = server.get("name", "") if isinstance(server, dict) else ""
        result.append(FightPerformance(
            fight_id=fight_id,
            player_name=r["name"],
            player_class=r["class"],
            player_spec=r["spec"],
            player_server=server_name,
            total_damage=r.get("total", 0),
            dps=r.get("amount", 0.0),
            total_healing=0,
            hps=0.0,
            parse_percentile=r.get("rankPercent"),
            ilvl_parse_percentile=r.get("bracketPercent"),
            deaths=r.get("deaths", 0),
            interrupts=r.get("interrupts", 0),
            dispels=r.get("dispels", 0),
            item_level=r.get("itemLevel"),
            is_my_character=r["name"] in my_character_names,
        ))
    return result


@dataclass
class IngestResult:
    fights: int
    performances: int


async def ingest_report(wcl, session, report_code: str, my_character_names: set[str] | None = None) -> IngestResult:
    """Fetch a report from WCL and persist it to the database."""
    from shukketsu.wcl.queries import REPORT_FIGHTS, REPORT_RANKINGS

    if my_character_names is None:
        my_character_names = set()

    # Fetch report data
    report_data = await wcl.query(
        REPORT_FIGHTS.replace("RATE_LIMIT", "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"),
        variables={"code": report_code},
    )
    report_info = report_data["reportData"]["report"]

    # Parse and merge report
    report = parse_report(report_info, report_code)
    session.add(report)

    # Parse fights
    fights = parse_fights(report_info["fights"], report_code)
    for fight in fights:
        session.add(fight)

    await session.flush()

    # Fetch rankings for each fight
    total_performances = 0
    fight_ids = [f.fight_id for f in fights]
    if fight_ids:
        rankings_data = await wcl.query(
            REPORT_RANKINGS.replace("RATE_LIMIT", "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"),
            variables={"code": report_code, "fightIDs": fight_ids},
        )
        rankings = rankings_data["reportData"]["report"]["rankings"]

        # Rankings come back as a dict keyed by fight ID
        if isinstance(rankings, dict):
            for fight in fights:
                fight_rankings = rankings.get(str(fight.fight_id), {})
                if isinstance(fight_rankings, dict):
                    roles = fight_rankings.get("roles", {})
                    for role_data in roles.values():
                        characters = role_data.get("characters", [])
                        perfs = parse_rankings_to_performances(
                            characters, fight.id, my_character_names,
                        )
                        for perf in perfs:
                            session.add(perf)
                        total_performances += len(perfs)

    logger.info(
        "Ingested report %s: %d fights, %d performances",
        report_code, len(fights), total_performances,
    )
    return IngestResult(fights=len(fights), performances=total_performances)
