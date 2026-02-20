"""Verify ranking scripts do NOT use session.begin() context manager.

The pipeline functions (ingest_all_rankings, ingest_all_speed_rankings)
manage their own transactions via commit()/rollback() per encounter batch.
Wrapping them in session.begin() causes "closed transaction" errors because
commit() inside the loop ends the context manager's transaction.
"""

import inspect

from shukketsu.scripts import pull_rankings, pull_speed_rankings


class TestRankingsTransactions:
    def test_pull_rankings_no_session_begin(self):
        """pull_rankings.run() must NOT wrap session in begin()."""
        source = inspect.getsource(pull_rankings.run)
        assert "session.begin()" not in source, (
            "session.begin() conflicts with per-encounter commit()/rollback()"
        )

    def test_pull_speed_rankings_no_session_begin(self):
        """pull_speed_rankings.run() must NOT wrap session in begin()."""
        source = inspect.getsource(pull_speed_rankings.run)
        assert "session.begin()" not in source, (
            "session.begin() conflicts with per-encounter commit()/rollback()"
        )
