from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.scripts.snapshot_progression import parse_args, run


def test_parse_args_defaults():
    args = parse_args([])
    assert args.character is None


def test_parse_args_character():
    args = parse_args(["--character", "TestRogue"])
    assert args.character == "TestRogue"


@patch("shukketsu.scripts.snapshot_progression.create_session_factory")
@patch("shukketsu.scripts.snapshot_progression.create_db_engine")
@patch("shukketsu.scripts.snapshot_progression.snapshot_all_characters")
@patch("shukketsu.scripts.snapshot_progression.get_settings")
async def test_run_snapshots(
    mock_get_settings,
    mock_snapshot,
    mock_create_engine,
    mock_create_factory,
):
    mock_settings = MagicMock()
    mock_get_settings.return_value = mock_settings

    mock_engine = AsyncMock()
    mock_create_engine.return_value = mock_engine
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_create_factory.return_value = mock_factory

    mock_snapshot.return_value = 5

    await run(character="TestRogue")

    mock_snapshot.assert_called_once_with(mock_session, character_name="TestRogue")
    mock_session.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()
