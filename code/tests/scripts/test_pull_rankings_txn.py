"""Verify ranking scripts use explicit transactions."""

import inspect

from shukketsu.scripts import pull_rankings, pull_speed_rankings


class TestRankingsTransactions:
    def test_pull_rankings_uses_session_begin(self):
        """pull_rankings.run() must wrap session in begin() for atomicity."""
        source = inspect.getsource(pull_rankings.run)
        assert "session.begin()" in source

    def test_pull_speed_rankings_uses_session_begin(self):
        """pull_speed_rankings.run() must wrap session in begin() for atomicity."""
        source = inspect.getsource(pull_speed_rankings.run)
        assert "session.begin()" in source
