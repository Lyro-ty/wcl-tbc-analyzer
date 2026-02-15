from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shukketsu.pipeline.ingest import IngestResult
from shukketsu.scripts.pull_my_logs import parse_args, run


def test_parse_args_report_code():
    args = parse_args(["--report-code", "abc123"])
    assert args.report_code == "abc123"


def test_parse_args_missing_report_code():
    with pytest.raises(SystemExit):
        parse_args([])


@patch("shukketsu.scripts.pull_my_logs.create_session_factory")
@patch("shukketsu.scripts.pull_my_logs.create_db_engine")
@patch("shukketsu.scripts.pull_my_logs.WCLClient")
@patch("shukketsu.scripts.pull_my_logs.ingest_report")
@patch("shukketsu.scripts.pull_my_logs.get_settings")
async def test_run_creates_client_and_ingests(
    mock_get_settings, mock_ingest, mock_wcl_client_cls,
    mock_create_engine, mock_create_factory,
):
    # Setup settings mock
    mock_settings = MagicMock()
    mock_settings.wcl.client_id = "test-id"
    mock_settings.wcl.client_secret.get_secret_value.return_value = "test-secret"
    mock_settings.wcl.oauth_url = "https://example.com/oauth"
    mock_settings.db.url = "postgresql+asyncpg://test:test@localhost/test"
    mock_get_settings.return_value = mock_settings

    # Setup engine/session mocks
    mock_engine = AsyncMock()
    mock_create_engine.return_value = mock_engine
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_create_factory.return_value = mock_factory

    # Setup WCL client mock
    mock_wcl = AsyncMock()
    mock_wcl_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wcl)
    mock_wcl_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup ingest mock
    mock_ingest.return_value = IngestResult(fights=3, performances=15)

    await run("abc123")

    mock_ingest.assert_called_once_with(mock_wcl, mock_session, "abc123")
    mock_session.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()
