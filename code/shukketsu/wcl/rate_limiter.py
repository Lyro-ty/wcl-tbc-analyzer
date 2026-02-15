import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """Tracks WCL API rate limit points and pauses requests when near the limit."""

    def __init__(self, safety_margin: float = 0.1) -> None:
        self.safety_margin = safety_margin
        self.limit_per_hour: int = 3600
        self._points_spent: int = 0
        self._points_reset_in: int = 0

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

    async def wait_if_needed(self) -> None:
        if not self.is_safe:
            logger.warning(
                "Rate limit near threshold (%d/%d), sleeping %ds",
                self._points_spent,
                self.limit_per_hour,
                self._points_reset_in,
            )
            await asyncio.sleep(self._points_reset_in)
