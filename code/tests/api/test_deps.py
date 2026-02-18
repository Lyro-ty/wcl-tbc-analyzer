"""Tests for FastAPI dependency providers."""

import asyncio

from shukketsu.api.deps import _cooldowns, cooldown


class TestCooldownRaceCondition:
    async def test_concurrent_requests_one_passes_cooldown(self):
        """Only one of two concurrent requests should pass the cooldown."""
        _cooldowns.clear()

        check = cooldown("test_race", seconds=60)
        # Extract the inner _check_cooldown function
        dep_fn = check.dependency

        passed = 0
        failed = 0

        async def try_cooldown():
            nonlocal passed, failed
            try:
                await dep_fn()
                passed += 1
            except Exception:
                failed += 1

        await asyncio.gather(try_cooldown(), try_cooldown())
        assert passed == 1, f"Expected 1 pass, got {passed}"
        assert failed == 1, f"Expected 1 fail, got {failed}"
        _cooldowns.clear()
