from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLAPIError, WCLClient, _parse_retry_after
from shukketsu.wcl.rate_limiter import RateLimiter

API_URL = "https://fresh.warcraftlogs.com/api/v2/client"
OAUTH_URL = "https://fresh.warcraftlogs.com/oauth/token"

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


@respx.mock
async def test_query_retries_on_429(auth, limiter):
    """429 responses trigger mark_throttled and retry via wait_if_needed."""
    _mock_oauth()
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={
            "data": {"test": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })

    respx.post(API_URL).mock(side_effect=side_effect)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with WCLClient(auth, limiter, api_url=API_URL) as client:
            data = await client.query("query { test }")

    assert data == {"test": True}
    assert call_count == 3


@respx.mock
async def test_query_retries_on_502(auth, limiter):
    """502/503/504 responses use exponential backoff."""
    _mock_oauth()
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(502)
        return httpx.Response(200, json={
            "data": {"ok": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })

    respx.post(API_URL).mock(side_effect=side_effect)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with WCLClient(auth, limiter, api_url=API_URL) as client:
            data = await client.query("query { ok }")

    assert data == {"ok": True}
    assert call_count == 2


@respx.mock
async def test_query_raises_400_immediately(auth, limiter):
    """Non-retryable HTTP errors are raised without retry."""
    _mock_oauth()
    respx.post(API_URL).mock(return_value=httpx.Response(400))

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.query("query { test }")


@respx.mock
async def test_429_marks_throttled_with_retry_after(auth, limiter):
    """429 with Retry-After header passes the value to rate limiter."""
    _mock_oauth()
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={
            "data": {"test": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })

    respx.post(API_URL).mock(side_effect=side_effect)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with WCLClient(auth, limiter, api_url=API_URL) as client:
            await client.query("query { test }")

    # After the successful response, throttle should be cleared
    assert limiter._throttled_until == 0.0


@respx.mock
async def test_429_exhausts_retries_raises(auth, limiter):
    """If all retries return 429, the final one raises HTTPStatusError."""
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"})
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with WCLClient(auth, limiter, api_url=API_URL) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.query("query { test }")
            assert exc_info.value.response.status_code == 429


@respx.mock
async def test_429_without_retry_after_uses_rate_limiter(auth, limiter):
    """429 without Retry-After header falls back to rate limiter data."""
    _mock_oauth()
    # Pre-populate rate limiter with reset info
    await limiter.update({
        "pointsSpentThisHour": 3500,
        "limitPerHour": 3600,
        "pointsResetIn": 300,
    })
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429)  # No Retry-After header
        return httpx.Response(200, json={
            "data": {"test": True},
            "extensions": {"rateLimitData": RATE_LIMIT_DATA},
        })

    respx.post(API_URL).mock(side_effect=side_effect)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async with WCLClient(auth, limiter, api_url=API_URL) as client:
            data = await client.query("query { test }")

    assert data == {"test": True}
    # wait_if_needed should have been called with a sleep
    # (the throttle uses _points_reset_in=300)
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert any(s >= 290 for s in sleep_calls), (
        f"Expected a sleep >= 290s from rate limiter fallback, got {sleep_calls}"
    )


@respx.mock
async def test_query_raises_on_non_dict_response(auth, limiter):
    """Non-dict response (e.g. a list) raises WCLAPIError."""
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(200, json=[{"unexpected": "list"}])
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        with pytest.raises(WCLAPIError, match="Expected dict"):
            await client.query("query { test }")


@respx.mock
async def test_query_raises_on_missing_data_key(auth, limiter):
    """Response dict without 'data' or 'errors' key raises WCLAPIError."""
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        with pytest.raises(WCLAPIError, match="missing 'data' key"):
            await client.query("query { test }")


@respx.mock
async def test_query_handles_error_without_message_key(auth, limiter):
    """GraphQL error objects without a 'message' key don't crash."""
    _mock_oauth()
    respx.post(API_URL).mock(
        return_value=httpx.Response(200, json={
            "errors": [{"code": "SOME_ERROR"}],
            "data": None,
        })
    )

    async with WCLClient(auth, limiter, api_url=API_URL) as client:
        with pytest.raises(WCLAPIError):
            await client.query("query { test }")


class TestParseRetryAfter:
    def test_valid_integer(self):
        resp = httpx.Response(429, headers={"Retry-After": "120"})
        assert _parse_retry_after(resp) == 120

    def test_no_header(self):
        resp = httpx.Response(429)
        assert _parse_retry_after(resp) is None

    def test_non_numeric(self):
        resp = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2025"})
        assert _parse_retry_after(resp) is None

    def test_zero(self):
        resp = httpx.Response(429, headers={"Retry-After": "0"})
        assert _parse_retry_after(resp) == 0
