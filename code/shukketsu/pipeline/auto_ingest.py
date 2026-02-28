"""Background service that polls WCL for new guild reports and auto-ingests them."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from shukketsu.db.models import Encounter, Report
from shukketsu.pipeline.ingest import ingest_report
from shukketsu.pipeline.speed_rankings import ingest_all_speed_rankings

logger = logging.getLogger(__name__)


class AutoIngestService:
    """Background service that polls WCL for new guild reports and auto-ingests them."""

    def __init__(self, settings, session_factory, wcl_factory):
        self.settings = settings
        self._session_factory = session_factory
        self._wcl_factory = wcl_factory  # callable returning async context manager
        self._task: asyncio.Task | None = None
        self._trigger_task: asyncio.Task | None = None
        self._poll_lock = asyncio.Lock()
        self._ingest_lock = asyncio.Lock()
        self._last_poll: datetime | None = None
        self._status: str = "idle"  # idle, polling, ingesting, error
        self._last_error: str | None = None
        self._stats: dict = {"polls": 0, "reports_ingested": 0, "errors": 0}
        self._consecutive_errors: int = 0
        self._benchmark_enabled = settings.benchmark.enabled
        self._benchmark_interval_days = settings.benchmark.refresh_interval_days
        self._benchmark_max_reports = settings.benchmark.max_reports_per_encounter
        self._benchmark_task: asyncio.Task | None = None
        self._last_benchmark_run: datetime | None = None
        self._last_speed_rankings_run: datetime | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.auto_ingest.enabled

    async def start(self):
        """Start the background polling loop."""
        if not self.enabled:
            logger.info("Auto-ingest is disabled")
            return
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "Auto-ingest started (interval=%dm)",
            self.settings.auto_ingest.poll_interval_minutes,
        )
        if self._benchmark_enabled:
            self._benchmark_task = asyncio.create_task(self._benchmark_loop())
            logger.info(
                "Benchmark auto-refresh enabled (every %d days)",
                self._benchmark_interval_days,
            )

    async def stop(self):
        """Stop the background polling loop."""
        if self._benchmark_task:
            self._benchmark_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._benchmark_task
        if self._trigger_task and not self._trigger_task.done():
            self._trigger_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._trigger_task
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._status = "idle"
        logger.info("Auto-ingest stopped")

    async def _benchmark_loop(self) -> None:
        """Weekly benchmark refresh loop: speed rankings then benchmarks."""
        interval = self._benchmark_interval_days * 86400  # days to seconds
        while True:
            await asyncio.sleep(interval)
            try:
                async with self._ingest_lock, self._wcl_factory() as wcl:
                    # Step 1: Refresh speed rankings
                    try:
                        await self._refresh_speed_rankings(wcl)
                    except Exception:
                        logger.exception(
                            "Speed rankings refresh failed,"
                            " continuing with benchmarks"
                        )

                    # Step 2: Run benchmark pipeline
                    from shukketsu.pipeline.benchmarks import (
                        run_benchmark_pipeline,
                    )

                    async with self._session_factory() as session:
                        result = await run_benchmark_pipeline(
                            wcl, session,
                            max_reports_per_encounter=(
                                self._benchmark_max_reports
                            ),
                        )
                        logger.info(
                            "Benchmark auto-refresh: discovered=%d,"
                            " ingested=%d, computed=%d",
                            result.discovered, result.ingested,
                            result.computed,
                        )
                self._last_benchmark_run = datetime.now(UTC)
            except Exception:
                logger.exception("Benchmark auto-refresh failed")

    async def _refresh_speed_rankings(self, wcl) -> None:
        """Refresh speed rankings for all encounters in benchmark zones."""
        zone_ids = self.settings.benchmark.zone_ids

        async with self._session_factory() as session:
            query = select(Encounter)
            if zone_ids:
                query = query.where(Encounter.zone_id.in_(zone_ids))
            result = await session.execute(query)
            encounter_ids = [e.id for e in result.scalars().all()]

        if not encounter_ids:
            logger.warning("No encounters found for speed rankings refresh")
            return

        logger.info(
            "Refreshing speed rankings for %d encounters",
            len(encounter_ids),
        )

        async with self._session_factory() as session:
            sr_result = await ingest_all_speed_rankings(
                wcl, session, encounter_ids,
            )
            logger.info(
                "Speed rankings refresh: fetched=%d, skipped=%d, errors=%d",
                sr_result.fetched, sr_result.skipped, len(sr_result.errors),
            )
        self._last_speed_rankings_run = datetime.now(UTC)

    async def _poll_loop(self):
        """Main polling loop with exponential backoff on errors."""
        base_interval = self.settings.auto_ingest.poll_interval_minutes * 60
        max_backoff = base_interval * 8
        while True:
            try:
                await self._poll_once()
                self._consecutive_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Error in auto-ingest poll loop")
                self._status = "error"
                self._last_error = str(exc)
                self._stats["errors"] += 1
                self._consecutive_errors += 1

            if self._consecutive_errors > 0:
                backoff = min(
                    base_interval * (2 ** (self._consecutive_errors - 1)),
                    max_backoff,
                )
                logger.warning(
                    "Auto-ingest backing off: %ds"
                    " (consecutive errors: %d)",
                    backoff, self._consecutive_errors,
                )
                await asyncio.sleep(backoff)
            else:
                await asyncio.sleep(base_interval)

    async def _poll_once(self):
        """Single poll: fetch guild reports, ingest new ones (mutex-protected)."""
        async with self._poll_lock:
            await self._poll_once_inner()

    async def _poll_once_inner(self):
        """Inner poll logic (called under _poll_lock)."""
        from shukketsu.db.models import MyCharacter
        from shukketsu.wcl.queries import GUILD_REPORTS

        guild_id = self.settings.guild.id
        if not guild_id:
            logger.warning("No guild ID configured, skipping poll")
            return

        self._status = "polling"
        self._last_poll = datetime.now(UTC)
        self._stats["polls"] += 1

        rate_limit_fragment = (
            "rateLimitData { pointsSpentThisHour limitPerHour pointsResetIn }"
        )

        async with self._wcl_factory() as wcl:
            # Fetch guild reports from WCL
            zone_ids = self.settings.auto_ingest.zone_ids
            if zone_ids:
                # WCL API only supports single zoneID, so poll per zone
                all_reports = []
                for zone_id in zone_ids:
                    variables = {
                        "guildID": guild_id,
                        "zoneID": zone_id,
                        "limit": 25,
                    }
                    data = await wcl.query(
                        GUILD_REPORTS.replace("RATE_LIMIT", rate_limit_fragment),
                        variables=variables,
                    )
                    reports_data = (
                        data.get("reportData", {})
                        .get("reports", {})
                        .get("data", [])
                    )
                    all_reports.extend(reports_data)
            else:
                variables = {"guildID": guild_id, "limit": 50}
                data = await wcl.query(
                    GUILD_REPORTS.replace("RATE_LIMIT", rate_limit_fragment),
                    variables=variables,
                )
                all_reports = (
                    data.get("reportData", {})
                    .get("reports", {})
                    .get("data", [])
                )

            if not all_reports:
                self._status = "idle"
                return

            # Check which reports are already in DB
            report_codes = [r["code"] for r in all_reports]
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Report.code).where(Report.code.in_(report_codes))
                )
                existing_codes = {row[0] for row in result}

            new_reports = [r for r in all_reports if r["code"] not in existing_codes]
            if not new_reports:
                self._status = "idle"
                return

            logger.info("Found %d new reports to ingest", len(new_reports))
            self._status = "ingesting"

            # Query registered character names for is_my_character flagging
            async with self._session_factory() as session:
                char_result = await session.execute(select(MyCharacter.name))
                my_names = {row[0] for row in char_result}

            # Ingest each new report (under ingest lock to prevent
            # concurrent poll + benchmark from ingesting the same report)
            cfg = self.settings.auto_ingest
            async with self._ingest_lock:
                for report_data in new_reports:
                    code = report_data["code"]
                    try:
                        async with (
                            self._session_factory() as session,
                            session.begin(),
                        ):
                            ingest_result = await ingest_report(
                                wcl, session, code,
                                my_character_names=my_names,
                                ingest_tables=cfg.with_tables,
                                ingest_events=cfg.with_events,
                            )
                        if ingest_result.enrichment_errors:
                            logger.warning(
                                "Enrichment errors for %s: %s",
                                code, ingest_result.enrichment_errors,
                            )
                        # Snapshot in separate transaction after commit
                        try:
                            async with (
                                self._session_factory() as session,
                                session.begin(),
                            ):
                                from shukketsu.pipeline.progression import (
                                    snapshot_all_characters,
                                )
                                await snapshot_all_characters(session)
                        except Exception:
                            logger.exception(
                                "Failed to auto-snapshot progression "
                                "after ingest of %s", code,
                            )
                        self._stats["reports_ingested"] += 1
                        logger.info(
                            "Auto-ingested report %s: %s",
                            code, report_data.get("title", ""),
                        )
                    except Exception as exc:
                        logger.exception(
                            "Failed to auto-ingest report %s", code,
                        )
                        self._last_error = str(exc)
                        self._stats["errors"] += 1

        self._status = "idle"

    async def trigger_now(self) -> dict:
        """Manual trigger, runs poll in background."""
        if self._poll_lock.locked():
            return {"status": "already_running", "message": "Poll already in progress"}
        self._trigger_task = asyncio.create_task(self._poll_once())
        return {"status": "triggered", "message": "Poll started in background"}

    def get_status(self) -> dict:
        """Get current service status."""
        return {
            "enabled": self.enabled,
            "status": self._status,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "last_error": self._last_error,
            "guild_id": self.settings.guild.id,
            "guild_name": self.settings.guild.name,
            "poll_interval_minutes": self.settings.auto_ingest.poll_interval_minutes,
            "consecutive_errors": self._consecutive_errors,
            "stats": dict(self._stats),
            "benchmark_enabled": self._benchmark_enabled,
            "last_benchmark_run": (
                self._last_benchmark_run.isoformat()
                if self._last_benchmark_run else None
            ),
            "last_speed_rankings_run": (
                self._last_speed_rankings_run.isoformat()
                if self._last_speed_rankings_run else None
            ),
        }
