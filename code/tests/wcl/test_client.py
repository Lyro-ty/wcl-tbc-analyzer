import httpx
import pytest
import respx

from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLAPIError, WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

API_URL = "https://www.warcraftlogs.com/api/v2/client"
OAUTH_URL = "https://www.warcraftlogs.com/oauth/token"

RATE_LIMIT_DATA = {
    "pointsSpentThisHour": 50,
    "limitPerHour": 3600,
    "pointsResetIn": 3500,
}


@pytest.fixture
def auth():
    return WCLAuth(client_id="test-id", client_secret="test-secret", oauth_url=OAUTH_URL)


@pytest.fixture
def limiter():
    return RateLimiter()


def _mock_oauth(route_oauth=None):
    """Set up OAuth mock returning a valid token."""
    return respx.post(OAUTH_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok123", "expires_in": 3600, "token_type": "bearer"}
        )
    )


@respx.mock
async def test_query_sends_graphql_post(auth, limiter):
    _mock_oauth()
    gql_route = respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={
            "data": {"reportData": {"report": {"title": "Test"}}},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        await client.query("query { reportData { report { title } } }")

    assert gql_route.called
    request = gql_route.calls.last.request
    assert request.headers["content-type"] == "application/json"
    assert request.headers["authorization"] == "Bearer tok123"


@respx.mock
async def test_query_updates_rate_limiter(auth, limiter):
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={
            "data": {"test": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        await client.query("query { test }")

    assert limiter.points_remaining == 3550


@respx.mock
async def test_query_parses_response(auth, limiter):
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={
            "data": {"reportData": {"report": {"title": "Gruul Kill"}}},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        data = await client.query("query { reportData { report { title } } }")

    assert data["reportData"]["report"]["title"] == "Gruul Kill"


@respx.mock
async def test_query_raises_on_graphql_errors(auth, limiter):
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={
            "errors": [{"message": "Field 'bad' not found"}],
            "data": None,
        })
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        with pytest.raises(WCLAPIError, match="Field 'bad' not found"):
            await client.query("query { bad }")


@respx.mock
async def test_query_passes_variables(auth, limiter):
    _mock_oauth()
    gql_route = respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={
            "data": {"test": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        await client.query("query($code: String!) { test }", variables={"code": "abc123"})

    import json
    body = json.loads(gql_route.calls.last.request.content)
    assert body["variables"] == {"code": "abc123"}
