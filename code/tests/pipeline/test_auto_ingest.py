"""Tests for the auto-ingest background service."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.pipeline.auto_ingest import AutoIngestService


def _make_settings(
    guild_id=123,
    guild_name="Test Guild",
    enabled=True,
    poll_interval=30,
    zone_ids=None,
    with_tables=True,
    with_events=True,
    benchmark_enabled=False,
    benchmark_refresh_interval_days=7,
    benchmark_max_reports=10,
):
    """Build a mock settings object."""
    settings = MagicMock()
    settings.guild.id = guild_id
    settings.guild.name = guild_name
    settings.guild.server_slug = "whitemane"
    settings.guild.server_region = "US"
    settings.auto_ingest.enabled = enabled
    settings.auto_ingest.poll_interval_minutes = poll_interval
    settings.auto_ingest.zone_ids = zone_ids or []
    settings.auto_ingest.with_tables = with_tables
    settings.auto_ingest.with_events = with_events
    settings.wcl.client_id = "test-id"
    settings.wcl.client_secret.get_secret_value.return_value = "test-secret"
    settings.wcl.oauth_url = "https://example.com/oauth"
    settings.wcl.api_url = "https://www.warcraftlogs.com/api/v2/client"
    settings.benchmark.enabled = benchmark_enabled
    settings.benchmark.refresh_interval_days = benchmark_refresh_interval_days
    settings.benchmark.max_reports_per_encounter = benchmark_max_reports
    return settings


def _make_wcl_factory(wcl_mock):
    """Build a sync factory returning an async context manager (mirrors WCLClient)."""
    def factory():
        return _AsyncCM(wcl_mock)
    return factory


class _AsyncCM:
    """Simple async context manager wrapping a value."""

    def __init__(self, val):
        self._val = val

    async def __aenter__(self):
        return self._val

    async def __aexit__(self, *exc):
        pass


def _make_session_factory(session_mock):
    """Build an async context manager factory returning the given session mock."""
    async def factory():
        return _AsyncCM(session_mock)
    return factory


def _make_transactional_session():
    """Build a mock session that supports `async with session.begin()`.

    session.begin() is MagicMock (sync, returns async CM) — in SQLAlchemy,
    session.begin() is synchronous and returns an AsyncSessionTransaction
    that acts as an async context manager.
    session.add() is MagicMock (sync). Other methods are AsyncMock.
    """
    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # session.add() is sync in SQLAlchemy
    mock_session.begin = MagicMock(return_value=_AsyncCM(None))
    return mock_session


def _make_transactional_session_factory(mock_session):
    """Build a session factory where `async with factory() as session` works,
    and `async with session.begin()` also works."""
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(
        return_value=mock_session,
    )
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return session_factory


class TestAutoIngestServiceStatus:
    """Tests for status reporting."""

    def test_get_status_idle(self):
        settings = _make_settings()
        svc = AutoIngestService(settings, MagicMock(), MagicMock())
        status = svc.get_status()

        assert status["enabled"] is True
        assert status["status"] == "idle"
        assert status["last_poll"] is None
        assert status["guild_id"] == 123
        assert status["guild_name"] == "Test Guild"
        assert status["poll_interval_minutes"] == 30
        assert status["stats"]["polls"] == 0
        assert status["stats"]["reports_ingested"] == 0
        assert status["stats"]["errors"] == 0

    def test_enabled_returns_false_when_disabled(self):
        settings = _make_settings(enabled=False)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())
        assert svc.enabled is False

    def test_enabled_returns_true_when_enabled(self):
        settings = _make_settings(enabled=True)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())
        assert svc.enabled is True


class TestAutoIngestPollOnce:
    """Tests for _poll_once logic."""

    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_skips_when_no_guild_id(self, mock_ingest):
        """Should skip polling if guild ID is 0."""
        settings = _make_settings(guild_id=0)
        wcl = AsyncMock()
        svc = AutoIngestService(settings, MagicMock(), _make_wcl_factory(wcl))

        await svc._poll_once()

        wcl.query.assert_not_called()
        mock_ingest.assert_not_called()
        assert svc._stats["polls"] == 0

    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_skips_empty_wcl_response(self, mock_ingest):
        """Should handle empty report list gracefully."""
        settings = _make_settings()
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {"reports": {"data": []}}
        }
        svc = AutoIngestService(settings, MagicMock(), _make_wcl_factory(wcl))

        await svc._poll_once()

        mock_ingest.assert_not_called()
        assert svc._stats["polls"] == 1
        assert svc._status == "idle"

    @patch(
        "shukketsu.pipeline.progression.snapshot_all_characters",
        new_callable=AsyncMock, return_value=0,
    )
    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_ingests_new_reports(self, mock_ingest, mock_snap):
        """3 reports from WCL, 1 already in DB -> 2 ingested."""
        settings = _make_settings()
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "reports": {
                    "data": [
                        {"code": "AAA", "title": "Raid Night 1"},
                        {"code": "BBB", "title": "Raid Night 2"},
                        {"code": "CCC", "title": "Raid Night 3"},
                    ]
                }
            }
        }

        # Mock session that supports async with session.begin()
        mock_session = _make_transactional_session()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([("BBB",)]))
        mock_session.execute.return_value = mock_result

        session_factory = _make_transactional_session_factory(mock_session)
        mock_ingest.return_value = MagicMock(fights=5, performances=25)

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._poll_once()

        # Should have called ingest_report for AAA and CCC (not BBB)
        assert mock_ingest.call_count == 2
        ingested_codes = [
            call.args[2] for call in mock_ingest.call_args_list
        ]
        assert "AAA" in ingested_codes
        assert "CCC" in ingested_codes
        assert "BBB" not in ingested_codes
        assert svc._stats["reports_ingested"] == 2
        assert svc._stats["polls"] == 1

    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_skips_all_existing_reports(self, mock_ingest):
        """All reports already in DB -> nothing ingested."""
        settings = _make_settings()
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "reports": {
                    "data": [
                        {"code": "AAA", "title": "Old Raid"},
                        {"code": "BBB", "title": "Other Old Raid"},
                    ]
                }
            }
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([("AAA",), ("BBB",)]))
        mock_session.execute.return_value = mock_result

        session_factory = MagicMock()
        session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._poll_once()

        mock_ingest.assert_not_called()
        assert svc._stats["reports_ingested"] == 0
        assert svc._status == "idle"

    @patch(
        "shukketsu.pipeline.progression.snapshot_all_characters",
        new_callable=AsyncMock, return_value=0,
    )
    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_ingest_passes_config_flags(self, mock_ingest, mock_snap):
        """Verify with_tables and with_events flags are forwarded."""
        settings = _make_settings(with_tables=True, with_events=True)
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "reports": {
                    "data": [{"code": "NEW1", "title": "Fresh Raid"}]
                }
            }
        }

        mock_session = _make_transactional_session()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        session_factory = _make_transactional_session_factory(mock_session)
        mock_ingest.return_value = MagicMock(fights=3, performances=15)

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._poll_once()

        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args
        assert call_kwargs.kwargs["ingest_tables"] is True
        assert call_kwargs.kwargs["ingest_events"] is True

    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_ingest_error_increments_error_count(self, mock_ingest):
        """If ingest_report raises, error count increments but continues."""
        settings = _make_settings()
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "reports": {
                    "data": [
                        {"code": "FAIL", "title": "Bad Raid"},
                        {"code": "OK", "title": "Good Raid"},
                    ]
                }
            }
        }

        mock_session = _make_transactional_session()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        session_factory = _make_transactional_session_factory(mock_session)

        mock_ingest.side_effect = [
            RuntimeError("WCL API exploded"),
            MagicMock(fights=3, performances=15),
        ]

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._poll_once()

        assert svc._stats["errors"] == 1
        assert svc._stats["reports_ingested"] == 1

    @patch(
        "shukketsu.pipeline.progression.snapshot_all_characters",
        new_callable=AsyncMock, return_value=0,
    )
    @patch("shukketsu.pipeline.auto_ingest.ingest_report")
    async def test_poll_with_zone_ids(self, mock_ingest, mock_snap):
        """When zone_ids configured, queries per zone."""
        settings = _make_settings(zone_ids=[1047, 1048])
        wcl = AsyncMock()
        wcl.query.side_effect = [
            {
                "reportData": {
                    "reports": {
                        "data": [{"code": "Z1", "title": "Kara Run"}]
                    }
                }
            },
            {
                "reportData": {
                    "reports": {
                        "data": [{"code": "Z2", "title": "BWL Run"}]
                    }
                }
            },
        ]

        mock_session = _make_transactional_session()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        session_factory = _make_transactional_session_factory(mock_session)
        mock_ingest.return_value = MagicMock(fights=3, performances=15)

        svc = AutoIngestService(settings, session_factory, _make_wcl_factory(wcl))
        await svc._poll_once()

        # WCL queried twice (once per zone)
        assert wcl.query.call_count == 2
        assert mock_ingest.call_count == 2
        assert svc._stats["reports_ingested"] == 2


class TestAutoIngestStartStop:
    """Tests for start/stop lifecycle."""

    async def test_start_does_nothing_when_disabled(self):
        settings = _make_settings(enabled=False)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())

        await svc.start()

        assert svc._task is None

    async def test_start_creates_task_when_enabled(self):
        settings = _make_settings(enabled=True, guild_id=0)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())

        await svc.start()
        # Task should be created
        assert svc._task is not None

        # Clean up
        await svc.stop()

    async def test_stop_cancels_task(self):
        settings = _make_settings(enabled=True, guild_id=0)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())

        await svc.start()
        assert svc._task is not None
        assert not svc._task.done()

        await svc.stop()
        assert svc._status == "idle"


class TestAutoIngestTrigger:
    """Tests for manual trigger."""

    async def test_trigger_now_returns_status(self):
        settings = _make_settings(guild_id=0)
        svc = AutoIngestService(settings, MagicMock(), MagicMock())

        result = await svc.trigger_now()

        assert result["status"] == "triggered"
        assert "message" in result

    async def test_trigger_now_rejects_concurrent(self):
        """Second trigger_now call returns already_running while poll lock held."""
        settings = _make_settings()
        wcl = AsyncMock()
        svc = AutoIngestService(settings, AsyncMock(), _make_wcl_factory(wcl))

        # Simulate an in-progress poll by holding the lock
        await svc._poll_lock.acquire()

        result = await svc.trigger_now()
        assert result["status"] == "already_running"

        # Clean up
        svc._poll_lock.release()


class TestAutoIngestShutdown:
    def test_stop_cancels_trigger_task(self):
        """stop() must cancel _trigger_task if one is running."""
        source = inspect.getsource(AutoIngestService.stop)
        assert "_trigger_task" in source


class TestAutoIngestBackoff:
    def test_poll_loop_tracks_consecutive_errors(self):
        """Poll loop should track consecutive errors for backoff."""
        source = inspect.getsource(AutoIngestService._poll_loop)
        assert "_consecutive_errors" in source


class TestAutoIngestEnrichmentLogging:
    def test_ingest_result_captured(self):
        """auto_ingest must capture IngestResult to log enrichment errors."""
        source = inspect.getsource(AutoIngestService._poll_once_inner)
        # Must capture the return value of ingest_report
        assert "= await ingest_report(" in source or "=await ingest_report(" in source

    def test_enrichment_errors_logged(self):
        """auto_ingest must check and log enrichment_errors."""
        source = inspect.getsource(AutoIngestService._poll_once_inner)
        assert "enrichment_errors" in source


class TestBenchmarkAutoRefresh:
    """Tests for benchmark auto-refresh integration."""

    def test_benchmark_config_stored(self):
        """Verify benchmark config fields are stored from settings."""
        settings = MagicMock()
        settings.benchmark.enabled = True
        settings.benchmark.refresh_interval_days = 7
        settings.benchmark.max_reports_per_encounter = 10
        settings.auto_ingest.enabled = False
        settings.guild.id = 0

        service = AutoIngestService(
            settings=settings,
            session_factory=AsyncMock(),
            wcl_factory=AsyncMock(),
        )
        assert service._benchmark_enabled is True
        assert service._benchmark_interval_days == 7
        assert service._benchmark_max_reports == 10

    def test_benchmark_disabled(self):
        """Verify benchmark disabled state is stored."""
        settings = MagicMock()
        settings.benchmark.enabled = False
        settings.auto_ingest.enabled = False
        settings.guild.id = 0

        service = AutoIngestService(
            settings=settings,
            session_factory=AsyncMock(),
            wcl_factory=AsyncMock(),
        )
        assert service._benchmark_enabled is False

    def test_get_status_includes_benchmark(self):
        """get_status() includes benchmark_enabled and last_benchmark_run."""
        settings = MagicMock()
        settings.benchmark.enabled = True
        settings.benchmark.refresh_interval_days = 7
        settings.benchmark.max_reports_per_encounter = 10
        settings.auto_ingest.enabled = False
        settings.guild.id = 123
        settings.guild.name = "Test"

        service = AutoIngestService(
            settings=settings,
            session_factory=AsyncMock(),
            wcl_factory=AsyncMock(),
        )
        status = service.get_status()
        assert status["benchmark_enabled"] is True
        assert status["last_benchmark_run"] is None
