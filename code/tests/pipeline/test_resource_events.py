"""Tests for resource events pipeline (compute snapshots + ingest)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.pipeline.resource_events import (
    _TARGET_SAMPLES,
    compute_resource_snapshots,
    ingest_resource_data_for_fight,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resource_event(
    source_id: int,
    timestamp: int,
    resource_type: int,
    amount: int,
    max_amount: int = 10000,
    resource_change: int = 0,
) -> dict:
    """Build a raw WCL ResourceChange event dict."""
    return {
        "timestamp": timestamp,
        "type": "resourcechange",
        "sourceID": source_id,
        "resourceChange": resource_change,
        "resourceChangeType": resource_type,
        "waste": 0,
        "classResources": [
            {"amount": amount, "max": max_amount, "type": resource_type}
        ],
    }


# ---------------------------------------------------------------------------
# compute_resource_snapshots - basic
# ---------------------------------------------------------------------------

class TestComputeResourceSnapshotsBasic:

    def test_basic_mana_tracking(self):
        """Computes min/max/avg for a single player's mana events."""
        actors = {1: "Lyro"}
        events = [
            _make_resource_event(1, 1000, 0, 8000),
            _make_resource_event(1, 2000, 0, 6000),
            _make_resource_event(1, 3000, 0, 4000),
            _make_resource_event(1, 4000, 0, 7000),
        ]

        result = compute_resource_snapshots(
            events, fight_id=42, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        snap = result[0]
        assert snap.fight_id == 42
        assert snap.player_name == "Lyro"
        assert snap.resource_type == "Mana"
        assert snap.min_value == 4000
        assert snap.max_value == 8000
        assert snap.avg_value == round((8000 + 6000 + 4000 + 7000) / 4, 1)
        assert snap.time_at_zero_ms == 0
        assert snap.time_at_zero_pct == 0.0


class TestComputeResourceSnapshotsMultiplePlayers:

    def test_two_players_different_resource_types(self):
        """Two players with different resource types produce separate snapshots."""
        actors = {1: "Mage", 2: "Warrior"}
        events = [
            _make_resource_event(1, 1000, 0, 5000),  # Mage - Mana
            _make_resource_event(1, 2000, 0, 3000),  # Mage - Mana
            _make_resource_event(2, 1000, 1, 50),     # Warrior - Rage
            _make_resource_event(2, 2000, 1, 80),     # Warrior - Rage
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 2
        by_name = {s.player_name: s for s in result}

        assert "Mage" in by_name
        assert by_name["Mage"].resource_type == "Mana"
        assert by_name["Mage"].min_value == 3000
        assert by_name["Mage"].max_value == 5000

        assert "Warrior" in by_name
        assert by_name["Warrior"].resource_type == "Rage"
        assert by_name["Warrior"].min_value == 50
        assert by_name["Warrior"].max_value == 80


class TestComputeResourceSnapshotsEmpty:

    def test_empty_events_returns_empty(self):
        """Empty events list returns empty result."""
        result = compute_resource_snapshots(
            [], fight_id=1, fight_duration_ms=10000, actors={1: "Lyro"},
        )
        assert result == []

    def test_zero_duration_returns_empty(self):
        """Zero fight duration returns empty result."""
        events = [_make_resource_event(1, 1000, 0, 5000)]
        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=0, actors={1: "Lyro"},
        )
        assert result == []


class TestComputeResourceSnapshotsTimeAtZero:

    def test_time_at_zero_calculated(self):
        """Events where resource hits 0 accumulate time_at_zero correctly."""
        actors = {1: "Mage"}
        # Fight: 10 seconds total
        # Events at: 1000, 2000 (zero), 4000 (non-zero), 6000 (zero), 8000 (non-zero)
        # Zero at 2000: time until next event = 4000-2000 = 2000ms
        # Zero at 6000: time until next event = 8000-6000 = 2000ms
        # Total zero time: 4000ms, pct = 4000/10000*100 = 40.0%
        events = [
            _make_resource_event(1, 1000, 0, 5000),
            _make_resource_event(1, 2000, 0, 0),
            _make_resource_event(1, 4000, 0, 3000),
            _make_resource_event(1, 6000, 0, 0),
            _make_resource_event(1, 8000, 0, 2000),
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        snap = result[0]
        assert snap.time_at_zero_ms == 4000
        assert snap.time_at_zero_pct == 40.0

    def test_time_at_zero_last_event(self):
        """When last event is at zero, time extends to end of fight."""
        actors = {1: "Mage"}
        # Events at: 1000 (5000 mana), 5000 (0 mana)
        # Zero at 5000: last event, extends to fight end.
        # Fight end approx = first_ts + duration = 1000 + 10000 = 11000
        # delta = 11000 - 5000 = 6000ms
        events = [
            _make_resource_event(1, 1000, 0, 5000),
            _make_resource_event(1, 5000, 0, 0),
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        snap = result[0]
        assert snap.time_at_zero_ms == 6000
        assert snap.time_at_zero_pct == 60.0


class TestComputeResourceSnapshotsUnknownSource:

    def test_unknown_source_skipped(self):
        """Events with sourceID not in actors dict are skipped."""
        actors = {1: "Mage"}
        events = [
            _make_resource_event(1, 1000, 0, 5000),   # Known player
            _make_resource_event(99, 2000, 0, 3000),   # Unknown source (NPC)
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        assert result[0].player_name == "Mage"


class TestComputeResourceSnapshotsSamplesJson:

    def test_samples_json_small_dataset(self):
        """With fewer events than target, all data points included in samples."""
        actors = {1: "Mage"}
        events = [
            _make_resource_event(1, 1000, 0, 8000),
            _make_resource_event(1, 2000, 0, 6000),
            _make_resource_event(1, 3000, 0, 4000),
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        samples = json.loads(result[0].samples_json)
        assert len(samples) == 3
        assert samples[0] == {"t": 1000, "v": 8000}
        assert samples[1] == {"t": 2000, "v": 6000}
        assert samples[2] == {"t": 3000, "v": 4000}

    def test_samples_json_downsampled(self):
        """With many events, samples are downsampled to ~TARGET_SAMPLES points."""
        actors = {1: "Mage"}
        num_events = _TARGET_SAMPLES * 3  # 150 events
        events = [
            _make_resource_event(1, i * 100, 0, 5000 + i)
            for i in range(num_events)
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=num_events * 100,
            actors=actors,
        )

        assert len(result) == 1
        samples = json.loads(result[0].samples_json)
        assert len(samples) == _TARGET_SAMPLES


class TestComputeResourceSnapshotsNoClassResources:

    def test_events_missing_class_resources_skipped(self):
        """Events without classResources field are skipped gracefully."""
        actors = {1: "Mage"}
        events = [
            {
                "timestamp": 1000,
                "type": "resourcechange",
                "sourceID": 1,
                "resourceChange": 500,
                "resourceChangeType": 0,
            },
            _make_resource_event(1, 2000, 0, 5000),
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        snap = result[0]
        # Only the second event has valid classResources
        assert snap.min_value == 5000
        assert snap.max_value == 5000

    def test_events_with_empty_class_resources_skipped(self):
        """Events with empty classResources list are skipped."""
        actors = {1: "Mage"}
        events = [
            {
                "timestamp": 1000,
                "type": "resourcechange",
                "sourceID": 1,
                "classResources": [],
            },
            _make_resource_event(1, 2000, 0, 5000),
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        assert result[0].min_value == 5000

    def test_events_with_null_class_resources_skipped(self):
        """Events with None classResources are skipped."""
        actors = {1: "Mage"}
        events = [
            {
                "timestamp": 1000,
                "type": "resourcechange",
                "sourceID": 1,
                "classResources": None,
            },
            _make_resource_event(1, 2000, 0, 5000),
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert len(result) == 1
        assert result[0].min_value == 5000


class TestComputeResourceSnapshotsUnknownResourceType:

    def test_unknown_resource_type_skipped(self):
        """Events with resource type not in RESOURCE_TYPE_NAMES are skipped."""
        actors = {1: "Rogue"}
        events = [
            _make_resource_event(1, 1000, 99, 50),  # Unknown resource type
        ]

        result = compute_resource_snapshots(
            events, fight_id=1, fight_duration_ms=10000, actors=actors,
        )

        assert result == []


# ---------------------------------------------------------------------------
# ingest_resource_data_for_fight (mocked end-to-end)
# ---------------------------------------------------------------------------

class TestIngestResourceDataForFight:

    async def test_ingest_resource_data_for_fight(self):
        """Mocked end-to-end: fetches events, computes, inserts snapshots."""
        wcl = AsyncMock()

        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        fight = MagicMock()
        fight.id = 42
        fight.fight_id = 7
        fight.start_time = 0
        fight.end_time = 60_000

        actors = {1: "Mage", 2: "Warrior"}

        raw_events = [
            _make_resource_event(1, 1000, 0, 8000),   # Mage mana
            _make_resource_event(1, 2000, 0, 6000),   # Mage mana
            _make_resource_event(2, 1000, 1, 50),      # Warrior rage
            _make_resource_event(2, 2000, 1, 80),      # Warrior rage
            _make_resource_event(99, 3000, 0, 1000),   # NPC, skipped
        ]

        async def _fake_fetch(*args, **kwargs):
            yield raw_events

        with patch(
            "shukketsu.pipeline.resource_events.fetch_all_events",
            side_effect=_fake_fetch,
        ):
            count = await ingest_resource_data_for_fight(
                wcl, session, "ABC123", fight, actors,
            )

        assert count == 2  # One snapshot per (player, resource_type)
        assert session.add.call_count == 2
        session.flush.assert_awaited_once()

        # Verify delete was called
        assert session.execute.await_count == 1

    async def test_ingest_resource_data_for_fight_empty(self):
        """No events from WCL results in 0 rows inserted."""
        wcl = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock()

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 1
        fight.start_time = 0
        fight.end_time = 60_000

        async def _fake_fetch_empty(*args, **kwargs):
            if False:
                yield

        with patch(
            "shukketsu.pipeline.resource_events.fetch_all_events",
            side_effect=_fake_fetch_empty,
        ):
            count = await ingest_resource_data_for_fight(
                wcl, session, "EMPTY", fight, {},
            )

        assert count == 0

    async def test_ingest_resource_data_for_fight_exception(self):
        """On exception, returns 0 and logs error."""
        wcl = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 1
        fight.start_time = 0
        fight.end_time = 60_000

        count = await ingest_resource_data_for_fight(
            wcl, session, "FAIL", fight, {},
        )

        assert count == 0
