import logging
from typing import Any

import httpx

from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://www.warcraftlogs.com/api/v2/client"


class WCLAPIError(Exception):
    """Raised when the WCL GraphQL API returns errors."""


class WCLClient:
    """Async GraphQL client for WCL API v2."""

    def __init__(
        self,
        auth: WCLAuth,
        rate_limiter: RateLimiter,
        *,
        api_url: str = DEFAULT_API_URL,
    ) -> None:
        self._auth = auth
        self._rate_limiter = rate_limiter
        self._api_url = api_url
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WCLClient":
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    async def query(
        self,
        graphql_query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self._http is not None, "Use WCLClient as an async context manager"

        await self._rate_limiter.wait_if_needed()

        token = await self._auth.get_token(self._http)

        body: dict[str, Any] = {"query": graphql_query}
        if variables:
            body["variables"] = variables

        response = await self._http.post(
            self._api_url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()

        result = response.json()

        # Update rate limiter from response extensions
        extensions = result.get("extensions", {})
        rate_limit_data = extensions.get("rateLimitData")
        if rate_limit_data:
            self._rate_limiter.update(rate_limit_data)

        # Check for GraphQL errors
        if "errors" in result and result["errors"]:
            messages = "; ".join(e["message"] for e in result["errors"])
            raise WCLAPIError(messages)

        return result["data"]
