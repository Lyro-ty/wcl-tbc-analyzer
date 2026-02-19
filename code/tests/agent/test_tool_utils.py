"""Tests for tool_utils module."""

from unittest.mock import AsyncMock, patch

from shukketsu.agent.tool_utils import (
    EVENT_DATA_HINT,
    TABLE_DATA_HINT,
    db_tool,
    grade_above,
    grade_below,
    wildcard,
    wildcard_or_none,
)


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
        # Non-sensitive details are preserved for LLM self-correction
        assert "some internal detail" in result


class TestWildcard:
    def test_wraps_value(self):
        assert wildcard("Lyro") == "%Lyro%"

    def test_wraps_empty_string(self):
        assert wildcard("") == "%%"

    def test_preserves_spaces(self):
        assert wildcard("some name") == "%some name%"


class TestWildcardOrNone:
    def test_wraps_value(self):
        assert wildcard_or_none("Lyro") == "%Lyro%"

    def test_returns_none_for_none(self):
        assert wildcard_or_none(None) is None

    def test_returns_none_for_empty(self):
        assert wildcard_or_none("") is None

    def test_returns_none_for_whitespace(self):
        assert wildcard_or_none("  ") is None


class TestGradeAbove:
    """grade_above: first tier where value >= threshold (higher is better)."""

    def test_excellent(self):
        result = grade_above(
            95, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "EXCELLENT"

    def test_good(self):
        result = grade_above(
            87, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"

    def test_fair(self):
        result = grade_above(
            80, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "FAIR"

    def test_default(self):
        result = grade_above(
            50, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "NEEDS WORK"

    def test_exact_threshold(self):
        result = grade_above(
            85, [(90, "EXCELLENT"), (85, "GOOD"), (75, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"

    def test_letter_grades(self):
        assert grade_above(92, [(90, "A"), (75, "B"), (60, "C"), (40, "D")], "F") == "A"
        assert grade_above(38, [(90, "A"), (75, "B"), (60, "C"), (40, "D")], "F") == "F"


class TestGradeBelow:
    """grade_below: first tier where value < threshold (lower is better)."""

    def test_excellent(self):
        result = grade_below(
            3, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "EXCELLENT"

    def test_good(self):
        result = grade_below(
            7, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"

    def test_default(self):
        result = grade_below(
            25, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "NEEDS WORK"

    def test_exact_threshold(self):
        # value == threshold means NOT below it, so should fall through
        result = grade_below(
            5, [(5, "EXCELLENT"), (10, "GOOD"), (20, "FAIR")], "NEEDS WORK"
        )
        assert result == "GOOD"


class TestHintConstants:
    def test_table_hint_mentions_flag(self):
        assert "--with-tables" in TABLE_DATA_HINT

    def test_event_hint_mentions_flag(self):
        assert "--with-events" in EVENT_DATA_HINT
