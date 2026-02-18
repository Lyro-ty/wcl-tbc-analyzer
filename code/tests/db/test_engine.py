"""Verify DB engine configuration."""

from unittest.mock import patch

from shukketsu.config import Settings
from shukketsu.db.engine import create_db_engine


class TestDbEngine:
    def test_engine_sets_statement_timeout(self):
        """Engine must configure PostgreSQL statement_timeout."""
        with patch(
            "shukketsu.db.engine.create_async_engine"
        ) as mock_create:
            mock_create.return_value = None
            settings = Settings()
            create_db_engine(settings)
            call_kwargs = mock_create.call_args[1]
            assert "connect_args" in call_kwargs
            server_settings = call_kwargs["connect_args"]["server_settings"]
            assert "statement_timeout" in server_settings
            assert server_settings["statement_timeout"] == "30000"
