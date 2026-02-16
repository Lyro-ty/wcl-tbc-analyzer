"""Tests for the seed_encounters CLI script."""

from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.scripts.seed_encounters import parse_args, run


def test_parse_args_zone_ids():
    args = parse_args(["--zone-ids", "100,200,300"])
    assert args.zone_ids == "100,200,300"


def test_parse_args_from_db():
    args = parse_args(["--from-db"])
    assert args.from_db is True


def test_parse_args_defaults():
    args = parse_args([])
    assert args.zone_ids is None
    assert args.from_db is False


@patch("shukketsu.scripts.seed_encounters.create_session_factory")
@patch("shukketsu.scripts.seed_encounters.create_db_engine")
@patch("shukketsu.scripts.seed_encounters.WCLClient")
@patch("shukketsu.scripts.seed_encounters.discover_and_seed_encounters")
@patch("shukketsu.scripts.seed_encounters.get_settings")
async def test_run_with_zone_ids(
    mock_get_settings,
    mock_discover,
    mock_wcl_client_cls,
    mock_create_engine,
    mock_create_factory,
):
    # Setup settings mock
    mock_settings = MagicMock()
    mock_settings.wcl.client_id = "test-id"
    mock_settings.wcl.client_secret.get_secret_value.return_value = "test-secret"
    mock_settings.wcl.oauth_url = "https://example.com/oauth"
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

    # Setup discover mock
    mock_discover.return_value = [{"id": 1, "name": "Boss"}]

    await run(zone_ids=[100, 200])

    mock_discover.assert_called_once_with(mock_wcl, mock_session, [100, 200])
    mock_session.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()
