import time

import httpx
import pytest
import respx

from shukketsu.wcl.auth import WCLAuth, WCLAuthError

OAUTH_URL = "https://www.warcraftlogs.com/oauth/token"


@pytest.fixture
def auth():
    return WCLAuth(
        client_id="test-id",
        client_secret="test-secret",
        oauth_url=OAUTH_URL,
    )


@respx.mock
async def test_get_token_fetches_new_token(auth):
    route = respx.post(OAUTH_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok123", "expires_in": 3600, "token_type": "bearer"}
        )
    )
    async with httpx.AsyncClient() as client:
        token = await auth.get_token(client)

    assert token == "tok123"
    assert route.called
    request = route.calls.last.request
    assert b"grant_type=client_credentials" in request.content


@respx.mock
async def test_get_token_caches_while_valid(auth):
    route = respx.post(OAUTH_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok123", "expires_in": 3600, "token_type": "bearer"}
        )
    )
    async with httpx.AsyncClient() as client:
        t1 = await auth.get_token(client)
        t2 = await auth.get_token(client)

    assert t1 == t2
    assert route.call_count == 1


@respx.mock
async def test_get_token_refreshes_on_expiry(auth):
    respx.post(OAUTH_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok-new", "expires_in": 3600, "token_type": "bearer"}
        )
    )
    async with httpx.AsyncClient() as client:
        await auth.get_token(client)
        # Force expiry
        auth._expires_at = time.monotonic() - 1
        token = await auth.get_token(client)

    assert token == "tok-new"


@respx.mock
async def test_get_token_raises_on_401(auth):
    respx.post(OAUTH_URL).mock(
        return_value=httpx.Response(401, json={"error": "invalid_client"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(WCLAuthError, match="401"):
            await auth.get_token(client)


@respx.mock
async def test_get_token_retries_on_500(auth):
    route = respx.post(OAUTH_URL).mock(
        side_effect=[
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(
                200, json={"access_token": "tok-retry", "expires_in": 3600, "token_type": "bearer"}
            ),
        ]
    )
    async with httpx.AsyncClient() as client:
        token = await auth.get_token(client)

    assert token == "tok-retry"
    assert route.call_count == 2
