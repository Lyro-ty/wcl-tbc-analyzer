"""Shared WCL client factory — one Auth, one RateLimiter, one httpx pool."""

import httpx

from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter


class WCLFactory:
    """Creates WCLClient instances that share auth, rate limiter, and HTTP pool."""

    def __init__(self, settings) -> None:
        self._auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        self._rate_limiter = RateLimiter()
        self._api_url = settings.wcl.api_url
        self._pool: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Open the shared HTTP connection pool."""
        self._pool = httpx.AsyncClient(timeout=30.0)

    async def stop(self) -> None:
        """Close the shared HTTP connection pool."""
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    def __call__(self) -> WCLClient:
        """Return a WCLClient sharing this factory's auth, limiter, and pool."""
        return WCLClient(
            self._auth,
            self._rate_limiter,
            api_url=self._api_url,
            http_client=self._pool,
        )
