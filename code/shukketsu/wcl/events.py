"""Paginated WCL events API fetcher."""

import logging

from shukketsu.wcl.queries import REPORT_EVENTS

logger = logging.getLogger(__name__)

RATE_LIMIT_FRAG = "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"


async def fetch_all_events(
    wcl,
    report_code: str,
    start_time: float,
    end_time: float,
    data_type: str,
    source_id: int | None = None,
) -> list[dict]:
    """Fetch all events of a given type, paginating through nextPageTimestamp.

    Args:
        wcl: WCLClient instance.
        report_code: WCL report code.
        start_time: Fight start timestamp (ms).
        end_time: Fight end timestamp (ms).
        data_type: WCL EventDataType (e.g. "Deaths", "Casts", "DamageDone").
        source_id: Optional actor source ID filter.

    Returns:
        Combined list of all event dicts across all pages.
    """
    query = REPORT_EVENTS.replace("RATE_LIMIT", RATE_LIMIT_FRAG)
    all_events: list[dict] = []
    current_start = start_time

    while True:
        variables: dict = {
            "code": report_code,
            "startTime": current_start,
            "endTime": end_time,
            "dataType": data_type,
        }
        if source_id is not None:
            variables["sourceID"] = source_id

        raw = await wcl.query(query, variables=variables)
        events_data = raw["reportData"]["report"]["events"]

        page_events = events_data.get("data", [])
        all_events.extend(page_events)

        next_page = events_data.get("nextPageTimestamp")
        if next_page is None:
            break

        current_start = next_page
        logger.debug(
            "Events pagination: fetched %d events so far, next page at %d",
            len(all_events), next_page,
        )

    logger.info(
        "Fetched %d %s events for %s (%.0f-%.0f)",
        len(all_events), data_type, report_code, start_time, end_time,
    )
    return all_events
