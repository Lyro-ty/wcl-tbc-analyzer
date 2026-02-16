from unittest.mock import AsyncMock, MagicMock

from shukketsu.pipeline.characters import list_characters, register_character


class TestRegisterCharacter:
    async def test_creates_new_character(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute.return_value = mock_result

        char = await register_character(
            session,
            "TestRogue",
            "faerlina",
            "us",
            "Rogue",
            "Combat",
        )

        assert char.name == "TestRogue"
        assert char.server_slug == "faerlina"
        assert char.server_region == "us"
        assert char.character_class == "Rogue"
        assert char.spec == "Combat"
        session.add.assert_called_once()
        session.flush.assert_called_once()

    async def test_updates_existing_character(self):
        existing = MagicMock()
        existing.name = "TestRogue"
        existing.server_slug = "faerlina"
        existing.server_region = "us"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        session = AsyncMock()
        session.execute.return_value = mock_result

        char = await register_character(
            session,
            "TestRogue",
            "faerlina",
            "us",
            "Rogue",
            "Assassination",
        )

        assert char.character_class == "Rogue"
        assert char.spec == "Assassination"
        session.add.assert_not_called()

    async def test_marks_fight_performances(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute.return_value = mock_result

        await register_character(
            session,
            "TestRogue",
            "faerlina",
            "us",
            "Rogue",
            "Combat",
        )

        # Should have two execute calls: SELECT + UPDATE
        assert session.execute.call_count == 2


class TestListCharacters:
    async def test_returns_all_characters(self):
        char1 = MagicMock(name="A", server_slug="s1")
        char2 = MagicMock(name="B", server_slug="s2")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [char1, char2]

        session = AsyncMock()
        session.execute.return_value = mock_result

        chars = await list_characters(session)
        assert len(chars) == 2

    async def test_returns_empty_list(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute.return_value = mock_result

        chars = await list_characters(session)
        assert chars == []
