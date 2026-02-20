import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """Tracks WCL API rate limit points and pauses requests when near the limit."""

    MAX_SLEEP_SECONDS: int = 3600

    def __init__(self, safety_margin: float = 0.1) -> None:
        self.safety_margin = safety_margin
        self.limit_per_hour: int = 3600
        self._points_spent: int = 0
        self._points_reset_in: int = 0
        self._throttled_until: float = 0.0  # monotonic time

    @property
    def points_remaining(self) -> int:
        return self.limit_per_hour - self._points_spent

    @property
    def is_safe(self) -> bool:
        threshold = self.limit_per_hour * (1 - self.safety_margin)
        return self._points_spent < threshold

    def update(self, rate_limit_data: dict[str, Any]) -> None:
        self._points_spent = rate_limit_data["pointsSpentThisHour"]
        self.limit_per_hour = rate_limit_data["limitPerHour"]
        self._points_reset_in = rate_limit_data["pointsResetIn"]
        logger.debug(
            "Rate limit: %d/%d points used, resets in %ds",
            self._points_spent,
            self.limit_per_hour,
            self._points_reset_in,
        )

    def mark_throttled(self, retry_after: int | None = None) -> None:
        """Record a 429 throttle so the next wait_if_needed() sleeps."""
        if retry_after is not None:
            wait = retry_after
        elif self._points_reset_in > 0:
            wait = self._points_reset_in
        else:
            wait = 60  # conservative fallback
        wait = max(1, min(wait, self.MAX_SLEEP_SECONDS))
        self._throttled_until = time.monotonic() + wait
        logger.warning(
            "Rate limited (429), will wait %ds before next request", wait,
        )

    async def wait_if_needed(self) -> None:
        # Honour 429 throttle first
        now = time.monotonic()
        if self._throttled_until > now:
            sleep_duration = self._throttled_until - now
            logger.warning(
                "Waiting %.0fs for rate limit reset (429 throttle)",
                sleep_duration,
            )
            await asyncio.sleep(sleep_duration)
            self._throttled_until = 0.0
            return

        if not self.is_safe:
            sleep_duration = max(1, min(self._points_reset_in, self.MAX_SLEEP_SECONDS))
            logger.warning(
                "Rate limit near threshold (%d/%d), sleeping %ds"
                " (raw reset_in=%ds)",
                self._points_spent,
                self.limit_per_hour,
                sleep_duration,
                self._points_reset_in,
            )
            await asyncio.sleep(sleep_duration)
