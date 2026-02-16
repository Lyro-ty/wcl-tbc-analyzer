from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shukketsu.pipeline.progression import (
    compute_progression_snapshot,
    snapshot_all_characters,
)


def _make_perf(dps=1000.0, parse=75.0, deaths=0):
    """Helper to create a mock FightPerformance."""
    perf = MagicMock()
    perf.dps = dps
    perf.parse_percentile = parse
    perf.deaths = deaths
    return perf


class TestComputeProgressionSnapshot:
    async def test_computes_snapshot(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_perf(dps=1500.0, parse=90.0, deaths=0),
            _make_perf(dps=1200.0, parse=70.0, deaths=1),
            _make_perf(dps=1800.0, parse=95.0, deaths=0),
        ]
        session.execute.return_value = mock_result

        character = MagicMock()
        character.id = 1
        character.name = "TestRogue"
        now = datetime.now(UTC)

        snapshot = await compute_progression_snapshot(session, character, 650, now)

        assert snapshot is not None
        assert snapshot.character_id == 1
        assert snapshot.encounter_id == 650
        assert snapshot.best_parse == pytest.approx(95.0)
        assert snapshot.median_parse == pytest.approx(90.0)
        assert snapshot.best_dps == pytest.approx(1800.0)
        assert snapshot.median_dps == pytest.approx(1500.0)
        assert snapshot.kill_count == 3
        assert snapshot.avg_deaths == pytest.approx(1 / 3)

    async def test_returns_none_no_data(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        character = MagicMock()
        character.id = 1
        character.name = "TestRogue"
        now = datetime.now(UTC)

        snapshot = await compute_progression_snapshot(session, character, 650, now)
        assert snapshot is None

    async def test_single_kill(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_perf(dps=1500.0, parse=85.0, deaths=0),
        ]
        session.execute.return_value = mock_result

        character = MagicMock()
        character.id = 1
        character.name = "TestRogue"
        now = datetime.now(UTC)

        snapshot = await compute_progression_snapshot(session, character, 650, now)

        assert snapshot is not None
        assert snapshot.kill_count == 1
        assert snapshot.best_parse == snapshot.median_parse == pytest.approx(85.0)
        assert snapshot.best_dps == snapshot.median_dps == pytest.approx(1500.0)

    async def test_handles_none_parse(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_perf(dps=1500.0, parse=None, deaths=0),
        ]
        session.execute.return_value = mock_result

        character = MagicMock()
        character.id = 1
        character.name = "TestRogue"
        now = datetime.now(UTC)

        snapshot = await compute_progression_snapshot(session, character, 650, now)

        assert snapshot is not None
        assert snapshot.best_parse is None
        assert snapshot.median_parse is None
        assert snapshot.best_dps == pytest.approx(1500.0)


class TestSnapshotAllCharacters:
    async def test_no_characters(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        count = await snapshot_all_characters(session)
        assert count == 0

    async def test_creates_snapshots(self):
        char = MagicMock()
        char.id = 1
        char.name = "TestRogue"

        perf = _make_perf(dps=1500.0, parse=90.0, deaths=0)

        session = AsyncMock()
        # First call: select characters
        # Second call: select encounter IDs
        # Third call: select performances
        char_result = MagicMock()
        char_result.scalars.return_value.all.return_value = [char]

        enc_result = MagicMock()
        enc_result.all.return_value = [(650,)]

        perf_result = MagicMock()
        perf_result.scalars.return_value.all.return_value = [perf]

        session.execute.side_effect = [char_result, enc_result, perf_result]

        count = await snapshot_all_characters(session)
        assert count == 1
        session.merge.assert_called_once()
        session.flush.assert_called_once()
