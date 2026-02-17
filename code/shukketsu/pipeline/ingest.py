import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select

from shukketsu.db.models import Encounter, Fight, FightPerformance, Report
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
    table_rows: int = 0
    event_rows: int = 0


async def ingest_report(
    wcl, session, report_code: str, my_character_names: set[str] | None = None,
    *, ingest_tables: bool = False, ingest_events: bool = False,
) -> IngestResult:
    """Fetch a report from WCL and persist it to the database."""
    from shukketsu.wcl.queries import REPORT_FIGHTS, REPORT_RANKINGS

    if my_character_names is None:
        my_character_names = set()

    # Fetch report data
    report_data = await wcl.query(
        REPORT_FIGHTS.replace(
            "RATE_LIMIT",
            "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }",
        ),
        variables={"code": report_code},
    )
    report_info = report_data["reportData"]["report"]

    # Parse and merge report (idempotent upsert by PK=code)
    report = parse_report(report_info, report_code)
    await session.merge(report)

    # Delete existing fights + performances for this report (delete-then-insert)
    existing_fight_ids = await session.execute(
        select(Fight.id).where(Fight.report_code == report_code)
    )
    fight_id_list = [r[0] for r in existing_fight_ids]
    if fight_id_list:
        await session.execute(
            delete(FightPerformance).where(FightPerformance.fight_id.in_(fight_id_list))
        )
        await session.execute(
            delete(Fight).where(Fight.report_code == report_code)
        )

    # Parse fights
    fights = parse_fights(report_info["fights"], report_code)

    # Auto-insert any unknown encounters as stubs
    encounter_ids = {f.encounter_id for f in fights}
    for eid in encounter_ids:
        fight_data = next(
            fd for fd in report_info["fights"] if fd.get("encounterID") == eid
        )
        await session.merge(Encounter(
            id=eid,
            name=fight_data.get("name", f"Unknown ({eid})"),
            zone_id=0,
            zone_name="Unknown",
            difficulty=fight_data.get("difficulty", 0),
        ))

    for fight in fights:
        session.add(fight)

    await session.flush()

    # Fetch rankings for each fight
    total_performances = 0
    fight_ids = [f.fight_id for f in fights]
    if fight_ids:
        rankings_data = await wcl.query(
            REPORT_RANKINGS.replace(
                "RATE_LIMIT",
                "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }",
            ),
            variables={"code": report_code, "fightIDs": fight_ids},
        )
        rankings = rankings_data["reportData"]["report"]["rankings"]

        # Rankings come back as {"data": [{"fightID": N, "roles": {...}}, ...]}
        rankings_list = []
        if isinstance(rankings, dict):
            rankings_list = rankings.get("data", [])
        elif isinstance(rankings, list):
            rankings_list = rankings

        # Index by fightID for lookup
        rankings_by_fight = {r["fightID"]: r for r in rankings_list if "fightID" in r}

        for fight in fights:
            fight_rankings = rankings_by_fight.get(fight.fight_id, {})
            roles = fight_rankings.get("roles", {})
            for role_data in roles.values():
                characters = role_data.get("characters", [])
                perfs = parse_rankings_to_performances(
                    characters, fight.id, my_character_names,
                )
                for perf in perfs:
                    session.add(perf)
                total_performances += len(perfs)

    # Optionally ingest table data (ability breakdowns, buff uptimes)
    table_rows = 0
    if ingest_tables and fights:
        from shukketsu.pipeline.table_data import ingest_table_data_for_fight

        # Build actor name-by-id map from masterData
        actor_name_by_id = {}
        master_data = report_info.get("masterData", {})
        for actor in master_data.get("actors", []):
            actor_name_by_id[actor["id"]] = actor["name"]

        for fight in fights:
            rows = await ingest_table_data_for_fight(
                wcl, session, report_code, fight, actor_name_by_id,
            )
            table_rows += rows

    # Optionally ingest event data (deaths, cast metrics, cooldowns)
    event_rows = 0
    if ingest_events and fights:
        from shukketsu.pipeline.event_data import ingest_event_data_for_report

        event_rows = await ingest_event_data_for_report(wcl, session, report_code)

    logger.info(
        "Ingested report %s: %d fights, %d performances, %d table rows, %d event rows",
        report_code, len(fights), total_performances, table_rows, event_rows,
    )
    return IngestResult(
        fights=len(fights), performances=total_performances,
        table_rows=table_rows, event_rows=event_rows,
    )
