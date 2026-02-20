from unittest.mock import MagicMock

from shukketsu.wcl.factory import WCLFactory


def _mock_settings():
    settings = MagicMock()
    settings.wcl.client_id = "test-id"
    settings.wcl.client_secret.get_secret_value.return_value = "test-secret"
    settings.wcl.oauth_url = "https://example.com/oauth/token"
    settings.wcl.api_url = "https://example.com/api/v2/client"
    return settings


class TestWCLFactory:
    def test_factory_shares_auth_and_limiter(self):
        """Two clients from the same factory share auth and rate limiter."""
        factory = WCLFactory(_mock_settings())
        client_a = factory()
        client_b = factory()
        assert client_a._auth is client_b._auth
        assert client_a._rate_limiter is client_b._rate_limiter

    async def test_factory_shares_http_pool(self):
        """Clients share the factory's HTTP connection pool."""
        factory = WCLFactory(_mock_settings())
        await factory.start()
        try:
            client = factory()
            assert client._http is factory._pool
            assert not client._owns_http
        finally:
            await factory.stop()

    async def test_factory_lifecycle(self):
        """start() creates pool, stop() closes it."""
        factory = WCLFactory(_mock_settings())
        assert factory._pool is None

        await factory.start()
        assert factory._pool is not None
        pool = factory._pool

        await factory.stop()
        assert factory._pool is None
        assert pool.is_closed

    def test_factory_without_start_owns_http(self):
        """Factory before start() creates clients that own their own HTTP pool."""
        factory = WCLFactory(_mock_settings())
        client = factory()
        assert client._http is None
        assert client._owns_http
