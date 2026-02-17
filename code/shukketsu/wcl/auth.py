import logging
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class WCLAuthError(Exception):
    """Raised when WCL authentication fails."""


def _is_server_error(response: httpx.Response) -> bool:
    return response.status_code >= 500


class WCLAuth:
    """OAuth2 client credentials auth for WCL API v2."""

    def __init__(self, client_id: str, client_secret: str, oauth_url: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._oauth_url = oauth_url
        self._token: str | None = None
        self._expires_at: float = 0

    async def get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token

        response = await self._request_token(client)

        if response.status_code == 401:
            raise WCLAuthError(f"401: {response.text}")
        if response.status_code >= 400:
            raise WCLAuthError(f"{response.status_code}: {response.text}")

        data = response.json()
        self._token = data["access_token"]
        # Refresh 60s before actual expiry
        self._expires_at = time.monotonic() + data["expires_in"] - 60
        logger.info("Obtained new WCL access token, expires in %ds", data["expires_in"])
        return self._token

    @retry(
        retry=(
            retry_if_result(_is_server_error)
            | retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout))
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request_token(self, client: httpx.AsyncClient) -> httpx.Response:
        return await client.post(
            self._oauth_url,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
