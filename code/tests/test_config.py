from shukketsu.config import LangfuseConfig, LLMConfig, Settings, get_settings


def test_default_settings_have_sane_defaults(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    settings = Settings(_env_file=None)
    assert settings.db.url == "postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu"
    assert settings.llm.model == "nemotron-3-nano:30b"
    assert "11434" in settings.llm.base_url
    assert settings.llm.api_key == "ollama"
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


def test_llm_max_tokens_default():
    cfg = LLMConfig()
    assert cfg.max_tokens == 4096


def test_llm_timeout_default():
    cfg = LLMConfig()
    assert cfg.timeout == 300


def test_langfuse_disabled_by_default():
    cfg = LangfuseConfig()
    assert cfg.enabled is False


def test_langfuse_default_host():
    cfg = LangfuseConfig()
    assert cfg.host == "http://localhost:3000"


def test_langfuse_config_on_settings():
    settings = Settings(_env_file=None)
    assert hasattr(settings, "langfuse")
    assert settings.langfuse.enabled is False


def test_langfuse_env_override(monkeypatch):
    monkeypatch.setenv("LANGFUSE__ENABLED", "true")
    monkeypatch.setenv("LANGFUSE__PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE__SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE__HOST", "http://langfuse:3000")
    settings = Settings(_env_file=None)
    assert settings.langfuse.enabled is True
    assert settings.langfuse.public_key == "pk-lf-test"
    assert settings.langfuse.secret_key == "sk-lf-test"
    assert settings.langfuse.host == "http://langfuse:3000"
