import asyncio
import time
from unittest.mock import AsyncMock, patch

from shukketsu.wcl.rate_limiter import RateLimiter


def test_initial_state():
    rl = RateLimiter()
    assert rl.points_remaining == rl.limit_per_hour
    assert rl.is_safe


def test_update_state():
    rl = RateLimiter()
    rl.update({"pointsSpentThisHour": 100, "limitPerHour": 3600, "pointsResetIn": 3500})
    assert rl.points_remaining == 3500
    assert rl.limit_per_hour == 3600


def test_is_safe_under_limit():
    rl = RateLimiter(safety_margin=0.1)
    rl.update({"pointsSpentThisHour": 100, "limitPerHour": 3600, "pointsResetIn": 3500})
    assert rl.is_safe


def test_is_not_safe_near_limit():
    rl = RateLimiter(safety_margin=0.1)
    rl.update({"pointsSpentThisHour": 3500, "limitPerHour": 3600, "pointsResetIn": 300})
    assert not rl.is_safe


def test_is_not_safe_at_limit():
    rl = RateLimiter(safety_margin=0.1)
    rl.update({"pointsSpentThisHour": 3600, "limitPerHour": 3600, "pointsResetIn": 100})
    assert not rl.is_safe


async def test_wait_if_needed_returns_immediately_when_safe():
    rl = RateLimiter()
    rl.update({"pointsSpentThisHour": 100, "limitPerHour": 3600, "pointsResetIn": 3500})
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await rl.wait_if_needed()
        mock_sleep.assert_not_called()


async def test_wait_if_needed_sleeps_when_not_safe():
    rl = RateLimiter(safety_margin=0.1)
    rl.update({"pointsSpentThisHour": 3500, "limitPerHour": 3600, "pointsResetIn": 300})
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await rl.wait_if_needed()
        mock_sleep.assert_called_once_with(300)


class TestRateLimiterSleepCap:
    def test_max_sleep_seconds_class_attr(self):
        """RateLimiter must have a MAX_SLEEP_SECONDS cap."""
        assert hasattr(RateLimiter, 'MAX_SLEEP_SECONDS')
        assert RateLimiter.MAX_SLEEP_SECONDS == 3600

    async def test_wait_sleeps_capped_duration(self, monkeypatch):
        """wait_if_needed() should sleep min(pointsResetIn, MAX_SLEEP_SECONDS)."""
        slept = []

        async def mock_sleep(duration):
            slept.append(duration)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        rl = RateLimiter()
        rl.update({
            "pointsSpentThisHour": 3500,
            "limitPerHour": 3600,
            "pointsResetIn": 7200,
        })
        await rl.wait_if_needed()
        assert slept[0] == 3600  # capped, not 7200

    async def test_wait_floors_at_one_second(self, monkeypatch):
        """wait_if_needed() must sleep at least 1s to prevent busy-wait."""
        slept = []

        async def mock_sleep(duration):
            slept.append(duration)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        rl = RateLimiter()
        rl.update({
            "pointsSpentThisHour": 3500,
            "limitPerHour": 3600,
            "pointsResetIn": 0,
        })
        await rl.wait_if_needed()
        assert slept[0] == 1  # floored at 1, not 0


class TestMarkThrottled:
    def test_mark_throttled_with_retry_after(self):
        """mark_throttled uses Retry-After value when provided."""
        rl = RateLimiter()
        before = time.monotonic()
        rl.mark_throttled(retry_after=120)
        assert rl._throttled_until >= before + 119  # allow 1s tolerance

    def test_mark_throttled_falls_back_to_reset_in(self):
        """mark_throttled uses _points_reset_in when no Retry-After."""
        rl = RateLimiter()
        rl.update({
            "pointsSpentThisHour": 3500,
            "limitPerHour": 3600,
            "pointsResetIn": 300,
        })
        before = time.monotonic()
        rl.mark_throttled(retry_after=None)
        assert rl._throttled_until >= before + 299

    def test_mark_throttled_fallback_60s(self):
        """mark_throttled uses 60s fallback when no data available."""
        rl = RateLimiter()
        before = time.monotonic()
        rl.mark_throttled(retry_after=None)
        assert rl._throttled_until >= before + 59

    def test_mark_throttled_capped_at_max(self):
        """mark_throttled caps sleep at MAX_SLEEP_SECONDS."""
        rl = RateLimiter()
        before = time.monotonic()
        rl.mark_throttled(retry_after=9999)
        assert rl._throttled_until <= before + 3601

    async def test_wait_if_needed_honours_throttle(self, monkeypatch):
        """wait_if_needed sleeps when mark_throttled was called."""
        slept = []

        async def mock_sleep(duration):
            slept.append(duration)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        rl = RateLimiter()
        # Set throttle to 10s in the future
        rl._throttled_until = time.monotonic() + 10
        await rl.wait_if_needed()
        assert len(slept) == 1
        assert 9 <= slept[0] <= 11  # ~10s
        assert rl._throttled_until == 0.0  # cleared after wait

    async def test_throttle_takes_priority_over_points(self, monkeypatch):
        """Throttle wait takes priority over points-based wait."""
        slept = []

        async def mock_sleep(duration):
            slept.append(duration)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        rl = RateLimiter()
        rl.update({
            "pointsSpentThisHour": 3500,
            "limitPerHour": 3600,
            "pointsResetIn": 300,
        })
        # Set throttle to 5s in the future
        rl._throttled_until = time.monotonic() + 5

        await rl.wait_if_needed()
        # Should sleep for throttle (~5s), not points (300s)
        assert len(slept) == 1
        assert slept[0] < 10

    async def test_expired_throttle_ignored(self, monkeypatch):
        """Expired throttle is ignored — falls through to points check."""
        slept = []

        async def mock_sleep(duration):
            slept.append(duration)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        rl = RateLimiter()
        rl._throttled_until = time.monotonic() - 10  # already expired
        rl.update({
            "pointsSpentThisHour": 100,
            "limitPerHour": 3600,
            "pointsResetIn": 3500,
        })
        await rl.wait_if_needed()
        assert len(slept) == 0  # safe, no sleep
