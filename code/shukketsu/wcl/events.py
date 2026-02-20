"""Paginated WCL events API fetcher."""

import logging

from shukketsu.wcl.queries import REPORT_EVENTS

logger = logging.getLogger(__name__)

RATE_LIMIT_FRAG = "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"
MAX_PAGES = 100


async def fetch_all_events(
    wcl,
    report_code: str,
    start_time: float,
    end_time: float,
    data_type: str,
    source_id: int | None = None,
    *,
    max_pages: int = MAX_PAGES,
):
    """Yield event pages as lists instead of accumulating all in memory.

    Args:
        wcl: WCLClient instance.
        report_code: WCL report code.
        start_time: Fight start timestamp (ms).
        end_time: Fight end timestamp (ms).
        data_type: WCL EventDataType (e.g. "Deaths", "Casts", "DamageDone").
        source_id: Optional actor source ID filter.
        max_pages: Maximum number of pages to fetch (safety limit).

    Yields:
        Lists of event dicts, one per API page.
    """
    query = REPORT_EVENTS.replace("RATE_LIMIT", RATE_LIMIT_FRAG)
    current_start = start_time
    total_fetched = 0
    page_count = 0

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
        total_fetched += len(page_events)
        page_count += 1
        if page_events:
            yield page_events

        next_page = events_data.get("nextPageTimestamp")
        if next_page is None:
            break

        # Guard against stuck pagination (same timestamp returned)
        if next_page <= current_start:
            logger.warning(
                "Stuck pagination for %s %s: nextPageTimestamp %d <= current %d, "
                "stopping after %d pages (%d events)",
                report_code, data_type, next_page, current_start,
                page_count, total_fetched,
            )
            break

        if page_count >= max_pages:
            logger.warning(
                "Max pages (%d) reached for %s %s, stopping with %d events",
                max_pages, report_code, data_type, total_fetched,
            )
            break

        current_start = next_page
        logger.debug(
            "Events pagination: fetched %d events so far, next page at %d",
            total_fetched, next_page,
        )

    logger.info(
        "Fetched %d %s events for %s in %d pages (%.0f-%.0f)",
        total_fetched, data_type, report_code, page_count, start_time, end_time,
    )
