from shukketsu.config import Settings, get_settings


def test_default_settings_have_sane_defaults(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    settings = Settings(_env_file=None)
    assert settings.db.url == "postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu"
    assert settings.llm.model == "nemotron"
    assert settings.debug is False


def test_env_override(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "test-id")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("DB__URL", "postgresql+asyncpg://other:other@host:5432/other")
    settings = Settings()
    assert settings.wcl.client_id == "test-id"
    assert settings.db.url.endswith("/other")


def test_wcl_secret_not_in_repr(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "super-secret")
    settings = Settings()
    assert "super-secret" not in repr(settings)


def test_get_settings_returns_same_instance(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()
