from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.scripts.register_character import parse_args, run


def test_parse_args_registration():
    args = parse_args([
        "--name",
        "TestRogue",
        "--server",
        "faerlina",
        "--region",
        "us",
        "--class-name",
        "Rogue",
        "--spec",
        "Combat",
    ])
    assert args.name == "TestRogue"
    assert args.server == "faerlina"
    assert args.region == "us"
    assert args.class_name == "Rogue"
    assert args.spec == "Combat"


def test_parse_args_list():
    args = parse_args(["--list"])
    assert args.list_chars is True


def test_parse_args_defaults():
    args = parse_args([])
    assert args.name is None
    assert args.list_chars is False


@patch("shukketsu.scripts.register_character.create_session_factory")
@patch("shukketsu.scripts.register_character.create_db_engine")
@patch("shukketsu.scripts.register_character.register_character")
@patch("shukketsu.scripts.register_character.get_settings")
async def test_run_registers_character(
    mock_get_settings,
    mock_register,
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

    mock_char = MagicMock()
    mock_char.name = "TestRogue"
    mock_char.id = 1
    mock_register.return_value = mock_char

    await run(
        name="TestRogue",
        server="faerlina",
        region="us",
        class_name="Rogue",
        spec="Combat",
    )

    mock_register.assert_called_once_with(
        mock_session,
        "TestRogue",
        "faerlina",
        "us",
        "Rogue",
        "Combat",
    )
    mock_session.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()


@patch("shukketsu.scripts.register_character.create_session_factory")
@patch("shukketsu.scripts.register_character.create_db_engine")
@patch("shukketsu.scripts.register_character.list_characters")
@patch("shukketsu.scripts.register_character.get_settings")
async def test_run_lists_characters(
    mock_get_settings,
    mock_list,
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

    mock_list.return_value = []

    await run(list_chars=True)

    mock_list.assert_called_once_with(mock_session)
    mock_engine.dispose.assert_called_once()
