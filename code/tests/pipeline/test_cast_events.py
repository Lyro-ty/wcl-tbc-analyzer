"""Tests for cast event pipeline (parse, metrics, cooldowns, cancels, ingest)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shukketsu.db.models import CastEvent
from shukketsu.pipeline.cast_events import (
    compute_cancelled_casts,
    compute_cast_metrics,
    compute_cooldown_usage,
    ingest_cast_events_for_fight,
    parse_cast_events,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    source_id: int,
    event_type: str,
    spell_id: int,
    ability_name: str,
    timestamp: int,
    target_name: str | None = None,
) -> dict:
    """Build a raw WCL cast event dict."""
    event = {
        "sourceID": source_id,
        "type": event_type,
        "timestamp": timestamp,
        "ability": {"name": ability_name, "guid": spell_id},
    }
    if target_name is not None:
        event["target"] = {"name": target_name}
    return event


def _make_cast_event(
    player_name: str,
    event_type: str,
    spell_id: int,
    ability_name: str,
    timestamp_ms: int,
    fight_id: int = 1,
    target_name: str | None = None,
) -> CastEvent:
    """Build a CastEvent ORM object for testing compute functions."""
    return CastEvent(
        fight_id=fight_id,
        player_name=player_name,
        timestamp_ms=timestamp_ms,
        spell_id=spell_id,
        ability_name=ability_name,
        event_type=event_type,
        target_name=target_name,
    )


# ---------------------------------------------------------------------------
# parse_cast_events
# ---------------------------------------------------------------------------

class TestParseCastEvents:

    def test_parse_cast_events_basic(self):
        """Maps raw WCL events to CastEvent ORM objects correctly."""
        actors = {1: "Lyro", 2: "Healer"}
        events = [
            _make_event(1, "begincast", 25304, "Frostbolt", 1000, "Gruul the Dragonkiller"),
            _make_event(1, "cast", 25304, "Frostbolt", 2500, "Gruul the Dragonkiller"),
            _make_event(2, "cast", 9474, "Flash of Light", 1500),
        ]

        result = parse_cast_events(events, fight_id=42, actors=actors)

        assert len(result) == 3
        # First event
        assert result[0].fight_id == 42
        assert result[0].player_name == "Lyro"
        assert result[0].timestamp_ms == 1000
        assert result[0].spell_id == 25304
        assert result[0].ability_name == "Frostbolt"
        assert result[0].event_type == "begincast"
        assert result[0].target_name == "Gruul the Dragonkiller"
        # Second event
        assert result[1].event_type == "cast"
        assert result[1].timestamp_ms == 2500
        # Third event (no target)
        assert result[2].player_name == "Healer"
        assert result[2].target_name is None

    def test_parse_cast_events_skips_npc_sources(self):
        """Events with sourceID not in actors (NPCs) are skipped."""
        actors = {1: "Lyro"}
        events = [
            _make_event(1, "cast", 100, "Mortal Strike", 1000),
            _make_event(99, "cast", 200, "Frostbolt Volley", 1500),  # NPC
            _make_event(1, "cast", 100, "Mortal Strike", 3000),
        ]

        result = parse_cast_events(events, fight_id=1, actors=actors)

        assert len(result) == 2
        assert all(r.player_name == "Lyro" for r in result)

    def test_parse_cast_events_skips_non_cast_types(self):
        """Events with type != 'cast'/'begincast' are skipped."""
        actors = {1: "Lyro"}
        events = [
            _make_event(1, "cast", 100, "Mortal Strike", 1000),
            {"sourceID": 1, "type": "damage", "timestamp": 1100,
             "ability": {"name": "Mortal Strike", "guid": 100}},
            {"sourceID": 1, "type": "heal", "timestamp": 1200,
             "ability": {"name": "Bandage", "guid": 300}},
        ]

        result = parse_cast_events(events, fight_id=1, actors=actors)

        assert len(result) == 1
        assert result[0].event_type == "cast"

    def test_parse_cast_events_empty(self):
        """Empty event list returns empty result."""
        result = parse_cast_events([], fight_id=1, actors={1: "Lyro"})
        assert result == []

    def test_parse_cast_events_missing_ability(self):
        """Events without ability dict get fallback name."""
        actors = {1: "Lyro"}
        events = [{"sourceID": 1, "type": "cast", "timestamp": 1000}]

        result = parse_cast_events(events, fight_id=1, actors=actors)

        assert len(result) == 1
        assert result[0].spell_id == 0
        assert result[0].ability_name == "Spell-0"


# ---------------------------------------------------------------------------
# compute_cast_metrics
# ---------------------------------------------------------------------------

class TestComputeCastMetrics:

    def test_compute_cast_metrics_basic(self):
        """Correct CPM and GCD uptime for a simple case."""
        # 3 casts over 60 seconds: CPM should be 3.0
        # Timestamps: 0, 10000, 20000 across a 60s fight
        # Gap 0->10000: active += min(1500, 10000) = 1500
        # Gap 10000->20000: active += min(1500, 10000) = 1500
        # Last cast: active += 1500
        # Total active = 4500, uptime = 4500/60000 * 100 = 7.5%
        fight_duration_ms = 60_000
        events = [
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 0),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 10_000),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 20_000),
        ]

        result = compute_cast_metrics(events, fight_duration_ms)

        assert "Lyro" in result
        m = result["Lyro"]
        assert m.total_casts == 3
        assert m.casts_per_minute == 3.0
        assert m.active_time_ms == 4500
        assert m.downtime_ms == 55_500
        assert m.gcd_uptime_pct == 7.5

    def test_compute_cast_metrics_high_uptime(self):
        """Casts at GCD intervals should yield ~100% uptime."""
        # 40 casts at 1500ms intervals = 60s fight
        fight_duration_ms = 60_000
        events = [
            _make_cast_event("Lyro", "cast", 100, "Frostbolt", i * 1500)
            for i in range(40)
        ]

        result = compute_cast_metrics(events, fight_duration_ms)

        m = result["Lyro"]
        assert m.total_casts == 40
        # 39 gaps of 1500ms each: min(1500,1500)=1500 each, + last 1500 = 60000
        assert m.active_time_ms == 60_000
        assert m.gcd_uptime_pct == 100.0
        assert m.downtime_ms == 0

    def test_compute_cast_metrics_gaps(self):
        """Identifies gaps > 2500ms correctly."""
        fight_duration_ms = 30_000
        # Casts at 0, 1500, 3000 then a 5000ms gap, then 8000
        events = [
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 0),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 1500),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 3000),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 8000),
        ]

        result = compute_cast_metrics(events, fight_duration_ms)

        m = result["Lyro"]
        assert m.gap_count == 1
        assert m.longest_gap_ms == 5000  # 8000 - 3000
        assert m.longest_gap_at_ms == 3000  # Gap starts at cast timestamp 3000
        assert m.avg_gap_ms == 5000.0

    def test_compute_cast_metrics_multiple_gaps(self):
        """Multiple gaps are tracked correctly."""
        fight_duration_ms = 30_000
        # 0, then 4000 (gap=4000>2500), then 8000 (gap=4000>2500)
        events = [
            _make_cast_event("Lyro", "cast", 100, "MS", 0),
            _make_cast_event("Lyro", "cast", 100, "MS", 4000),
            _make_cast_event("Lyro", "cast", 100, "MS", 8000),
        ]

        result = compute_cast_metrics(events, fight_duration_ms)

        m = result["Lyro"]
        assert m.gap_count == 2
        assert m.longest_gap_ms == 4000
        assert m.avg_gap_ms == 4000.0

    def test_compute_cast_metrics_ignores_begincast(self):
        """Only 'cast' events count toward metrics, not 'begincast'."""
        fight_duration_ms = 60_000
        events = [
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 0),
            _make_cast_event("Lyro", "cast", 100, "Frostbolt", 2000),
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 3000),
            _make_cast_event("Lyro", "cast", 100, "Frostbolt", 5000),
        ]

        result = compute_cast_metrics(events, fight_duration_ms)

        m = result["Lyro"]
        assert m.total_casts == 2  # Only "cast" types

    def test_compute_cast_metrics_zero_duration(self):
        """Zero fight duration returns empty dict."""
        events = [_make_cast_event("Lyro", "cast", 100, "MS", 0)]
        result = compute_cast_metrics(events, 0)
        assert result == {}

    def test_compute_cast_metrics_multiple_players(self):
        """Metrics are computed independently per player."""
        fight_duration_ms = 60_000
        events = [
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 0),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 10_000),
            _make_cast_event("Healer", "cast", 200, "Flash of Light", 0),
        ]

        result = compute_cast_metrics(events, fight_duration_ms)

        assert "Lyro" in result
        assert "Healer" in result
        assert result["Lyro"].total_casts == 2
        assert result["Healer"].total_casts == 1


# ---------------------------------------------------------------------------
# compute_cooldown_usage
# ---------------------------------------------------------------------------

class TestComputeCooldownUsage:

    def test_compute_cooldown_usage_basic(self):
        """Correct efficiency calculation for a Warrior cooldown."""
        # Death Wish (12292): 180s CD. In a 360s fight: max_possible = 360000/180000 + 1 = 3
        fight_duration_ms = 360_000
        player_class_map = {"Lyro": "Warrior"}
        events = [
            _make_cast_event("Lyro", "cast", 12292, "Death Wish", 0),
            _make_cast_event("Lyro", "cast", 12292, "Death Wish", 180_000),
            # Also some non-cooldown casts
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 1000),
        ]

        result = compute_cooldown_usage(events, fight_duration_ms, player_class_map)

        # Warrior has 3 cooldowns in CLASSIC_COOLDOWNS
        dw = [r for r in result if r.spell_id == 12292]
        assert len(dw) == 1
        assert dw[0].times_used == 2
        assert dw[0].max_possible_uses == 3
        assert dw[0].efficiency_pct == round(2 / 3 * 100, 1)
        assert dw[0].first_use_ms == 0
        assert dw[0].last_use_ms == 180_000

    def test_compute_cooldown_usage_no_casts(self):
        """Cooldown with 0 uses shows 0% efficiency."""
        fight_duration_ms = 180_000
        player_class_map = {"Lyro": "Warrior"}
        events: list[CastEvent] = []

        result = compute_cooldown_usage(events, fight_duration_ms, player_class_map)

        dw = [r for r in result if r.spell_id == 12292]
        assert len(dw) == 1
        assert dw[0].times_used == 0
        assert dw[0].efficiency_pct == 0.0
        assert dw[0].first_use_ms is None
        assert dw[0].last_use_ms is None

    def test_compute_cooldown_usage_unknown_class(self):
        """Player with unknown class gets no cooldown entries."""
        events = [_make_cast_event("Lyro", "cast", 100, "MS", 0)]
        result = compute_cooldown_usage(events, 60_000, {"Lyro": "DeathKnight"})
        player_entries = [r for r in result if r.player_name == "Lyro"]
        assert player_entries == []

    def test_compute_cooldown_usage_zero_duration(self):
        """Zero fight duration returns empty list."""
        result = compute_cooldown_usage([], 0, {"Lyro": "Warrior"})
        assert result == []

    def test_compute_cooldown_usage_ignores_begincast(self):
        """Only 'cast' events count toward cooldown usage."""
        fight_duration_ms = 180_000
        player_class_map = {"Lyro": "Warrior"}
        events = [
            _make_cast_event("Lyro", "begincast", 12292, "Death Wish", 0),
            _make_cast_event("Lyro", "cast", 12292, "Death Wish", 500),
        ]

        result = compute_cooldown_usage(events, fight_duration_ms, player_class_map)

        dw = [r for r in result if r.spell_id == 12292]
        assert dw[0].times_used == 1


# ---------------------------------------------------------------------------
# compute_cancelled_casts
# ---------------------------------------------------------------------------

class TestComputeCancelledCasts:

    def test_compute_cancelled_casts_basic(self):
        """Correct cancel count and percentage."""
        events = [
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 0),
            _make_cast_event("Lyro", "cast", 100, "Frostbolt", 2000),
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 3000),
            # Second Frostbolt cancelled (no matching cast)
            _make_cast_event("Lyro", "begincast", 200, "Fireball", 5000),
            _make_cast_event("Lyro", "cast", 200, "Fireball", 7000),
        ]

        result = compute_cancelled_casts(events)

        assert "Lyro" in result
        cc = result["Lyro"]
        assert cc.total_begins == 3
        assert cc.total_completions == 2
        assert cc.cancel_count == 1
        assert cc.cancel_pct == round(1 / 3 * 100, 1)

    def test_compute_cancelled_casts_no_cancels(self):
        """All casts complete -> 0 cancels."""
        events = [
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 0),
            _make_cast_event("Lyro", "cast", 100, "Frostbolt", 2000),
        ]

        result = compute_cancelled_casts(events)

        cc = result["Lyro"]
        assert cc.cancel_count == 0
        assert cc.cancel_pct == 0.0

    def test_compute_cancelled_casts_top_cancelled_json(self):
        """Top cancelled spells are correctly computed as JSON."""
        events = [
            # 3 Frostbolt begins, 1 completion -> 2 cancels
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 0),
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 1000),
            _make_cast_event("Lyro", "begincast", 100, "Frostbolt", 2000),
            _make_cast_event("Lyro", "cast", 100, "Frostbolt", 3000),
            # 2 Fireball begins, 1 completion -> 1 cancel
            _make_cast_event("Lyro", "begincast", 200, "Fireball", 4000),
            _make_cast_event("Lyro", "begincast", 200, "Fireball", 5000),
            _make_cast_event("Lyro", "cast", 200, "Fireball", 6000),
        ]

        result = compute_cancelled_casts(events)

        cc = result["Lyro"]
        assert cc.cancel_count == 3
        assert cc.top_cancelled_json is not None
        top = json.loads(cc.top_cancelled_json)
        assert len(top) == 2
        # Frostbolt (2 cancels) should be first
        assert top[0]["spell_id"] == 100
        assert top[0]["cancel_count"] == 2
        assert top[1]["spell_id"] == 200
        assert top[1]["cancel_count"] == 1

    def test_compute_cancelled_casts_only_casts_no_begins(self):
        """Player with only 'cast' events (instants) has 0 begins, 0 cancels."""
        events = [
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 0),
            _make_cast_event("Lyro", "cast", 100, "Mortal Strike", 1500),
        ]

        result = compute_cancelled_casts(events)

        cc = result["Lyro"]
        assert cc.total_begins == 0
        assert cc.total_completions == 2
        assert cc.cancel_count == 0
        assert cc.cancel_pct == 0.0
        assert cc.top_cancelled_json is None

    def test_compute_cancelled_casts_empty(self):
        """Empty events returns empty dict."""
        result = compute_cancelled_casts([])
        assert result == {}


# ---------------------------------------------------------------------------
# ingest_cast_events_for_fight (mocked end-to-end)
# ---------------------------------------------------------------------------

class TestIngestCastEventsForFight:

    @pytest.mark.asyncio
    async def test_ingest_cast_events_for_fight(self):
        """Mocked end-to-end: fetches events, parses, inserts all tables."""
        # Mock WCL client
        wcl = AsyncMock()

        # Mock session
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        # Mock fight
        fight = MagicMock()
        fight.id = 42
        fight.fight_id = 7
        fight.start_time = 0
        fight.end_time = 60_000
        fight.report_code = "ABC123"

        actors = {1: "Lyro", 2: "Healer"}
        player_class_map = {"Lyro": "Warrior", "Healer": "Priest"}

        # Mock fetch_all_events as async generator yielding one page
        raw_events = [
            _make_event(1, "begincast", 100, "Slam", 0),
            _make_event(1, "cast", 100, "Slam", 1500),
            _make_event(1, "cast", 200, "Mortal Strike", 3000),
            _make_event(2, "cast", 300, "Flash of Light", 1000),
            _make_event(99, "cast", 400, "NPC Spell", 2000),  # NPC, skipped
        ]

        async def _fake_fetch(*args, **kwargs):
            yield raw_events

        with patch(
            "shukketsu.pipeline.cast_events.fetch_all_events",
            side_effect=_fake_fetch,
        ):
            total = await ingest_cast_events_for_fight(
                wcl, session, "ABC123", fight, actors, player_class_map,
            )

        # Should have inserted rows:
        #   4 CastEvent (begincast+cast for Lyro, cast for Healer; NPC skipped)
        #   2 CastMetric (Lyro + Healer)
        #   N CooldownUsage (Warrior+Priest cooldowns)
        #   2 CancelledCast (Lyro + Healer)
        assert total > 0
        assert session.add.call_count > 0
        session.flush.assert_awaited_once()

        # Verify 4 delete calls (one per table)
        assert session.execute.await_count == 4

    @pytest.mark.asyncio
    async def test_ingest_cast_events_for_fight_empty(self):
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
            # Empty async generator — yields nothing
            if False:
                yield

        with patch(
            "shukketsu.pipeline.cast_events.fetch_all_events",
            side_effect=_fake_fetch_empty,
        ):
            total = await ingest_cast_events_for_fight(
                wcl, session, "ABC", fight, {}, {},
            )

        assert total == 0

    @pytest.mark.asyncio
    async def test_ingest_cast_events_for_fight_exception(self):
        """On exception, error propagates to caller (outer handler in ingest.py)."""
        wcl = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        fight = MagicMock()
        fight.id = 1
        fight.fight_id = 1
        fight.start_time = 0
        fight.end_time = 60_000

        with pytest.raises(RuntimeError, match="DB error"):
            await ingest_cast_events_for_fight(
                wcl, session, "ABC", fight, {}, {},
            )
