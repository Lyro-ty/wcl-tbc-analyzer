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
