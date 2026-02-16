import httpx
import pytest
import respx

from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLAPIError, WCLClient, _is_retryable
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


class TestIsRetryable:
    def test_429_is_retryable(self):
        resp = httpx.Response(429)
        req = httpx.Request("POST", API_URL)
        exc = httpx.HTTPStatusError("rate limited", request=req, response=resp)
        assert _is_retryable(exc) is True

    def test_502_is_retryable(self):
        resp = httpx.Response(502)
        req = httpx.Request("POST", API_URL)
        exc = httpx.HTTPStatusError("bad gateway", request=req, response=resp)
        assert _is_retryable(exc) is True

    def test_400_is_not_retryable(self):
        resp = httpx.Response(400)
        req = httpx.Request("POST", API_URL)
        exc = httpx.HTTPStatusError("bad request", request=req, response=resp)
        assert _is_retryable(exc) is False

    def test_connect_error_is_retryable(self):
        exc = httpx.ConnectError("Connection refused")
        assert _is_retryable(exc) is True

    def test_read_timeout_is_retryable(self):
        exc = httpx.ReadTimeout("Read timed out")
        assert _is_retryable(exc) is True

    def test_generic_exception_not_retryable(self):
        assert _is_retryable(ValueError("nope")) is False


@respx.mock
async def test_query_retries_on_429(auth, limiter):
    _mock_oauth()
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return httpx.Response(429)
        return httpx.Response(200, json={
            "data": {"test": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })

    respx.post(API_URL).mock(side_effect=side_effect)

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        data = await client.query("query { test }")

    assert data == {"test": True}
    assert call_count == 3
