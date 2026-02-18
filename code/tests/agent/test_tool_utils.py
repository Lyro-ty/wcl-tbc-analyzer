"""Tests for tool_utils module."""

from unittest.mock import AsyncMock, patch

from shukketsu.agent.tool_utils import db_tool


class TestDbToolErrorSanitization:
    async def test_error_message_does_not_leak_sql(self):
        """Tool errors must not include raw SQL or connection details."""
        @db_tool
        async def bad_tool(session, name: str) -> str:
            """A tool that raises an error with SQL details."""
            raise Exception(
                '(sqlalchemy.exc.ProgrammingError) relation "secret_table" '
                'at postgresql://user:pass@host:5432/db'
            )

        mock_session = AsyncMock()
        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await bad_tool.ainvoke({"name": "test"})

        assert "postgresql://" not in result
        assert "pass@" not in result
        assert "secret_table" not in result
        assert "Error" in result

    async def test_error_includes_tool_name(self):
        """Error message should include the tool function name."""
        @db_tool
        async def my_failing_tool(session, x: int) -> str:
            """A tool that raises ValueError."""
            raise ValueError("some internal detail")

        mock_session = AsyncMock()
        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await my_failing_tool.ainvoke({"x": 42})

        assert "my_failing_tool" in result
        assert "some internal detail" not in result
