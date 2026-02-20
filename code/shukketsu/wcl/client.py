import asyncio
import logging
from typing import Any

import httpx

from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://fresh.warcraftlogs.com/api/v2/client"

MAX_RETRIES = 5
RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})


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
        """Execute a GraphQL query with rate-limit-aware retries.

        429 responses: sleep until the WCL rate limit resets (up to 1 hour),
        then retry.  502/503/504 and network errors: exponential backoff.
        """
        if self._http is None:
            raise RuntimeError("Use WCLClient as an async context manager")

        last_exc: BaseException | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            await self._rate_limiter.wait_if_needed()

            token = await self._auth.get_token(self._http)

            body: dict[str, Any] = {"query": graphql_query}
            if variables:
                body["variables"] = variables

            try:
                response = await self._http.post(
                    self._api_url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES:
                    raise
                wait = min(2 ** attempt * 2, 120)
                logger.warning(
                    "Network error (attempt %d/%d), retrying in %ds: %s",
                    attempt, MAX_RETRIES, wait, exc,
                )
                await asyncio.sleep(wait)
                continue

            # --- 429: rate-limited — sleep for the reset window, not backoff ---
            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                self._rate_limiter.mark_throttled(retry_after)
                if attempt == MAX_RETRIES:
                    response.raise_for_status()
                continue  # wait_if_needed() at top of loop will sleep

            # --- 5xx: server error — exponential backoff ---
            if response.status_code in RETRYABLE_STATUS_CODES:
                last_exc = httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=response.request,
                    response=response,
                )
                if attempt == MAX_RETRIES:
                    response.raise_for_status()
                wait = min(2 ** attempt * 2, 120)
                logger.warning(
                    "Server error %d (attempt %d/%d), retrying in %ds",
                    response.status_code, attempt, MAX_RETRIES, wait,
                )
                await asyncio.sleep(wait)
                continue

            # --- Other errors: raise immediately ---
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

        # Should not reach here, but satisfy type checker
        if last_exc:
            raise last_exc
        raise RuntimeError("Retry loop exhausted unexpectedly")


def _parse_retry_after(response: httpx.Response) -> int | None:
    """Extract Retry-After header as integer seconds, or None."""
    raw = response.headers.get("Retry-After")
    if raw and raw.isdigit():
        return int(raw)
    return None
