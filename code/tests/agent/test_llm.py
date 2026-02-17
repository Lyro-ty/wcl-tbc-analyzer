from langchain_openai import ChatOpenAI

from shukketsu.agent.llm import create_llm
from shukketsu.config import Settings


def test_create_llm_returns_chat_model(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    settings = Settings()
    llm = create_llm(settings)
    assert isinstance(llm, ChatOpenAI)


def test_llm_uses_configured_model(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    monkeypatch.setenv("LLM__MODEL", "test-model")
    settings = Settings()
    llm = create_llm(settings)
    assert llm.model_name == "test-model"


def test_llm_uses_configured_endpoint(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    monkeypatch.setenv("LLM__BASE_URL", "http://myhost:9999/v1")
    settings = Settings()
    llm = create_llm(settings)
    assert str(llm.openai_api_base) == "http://myhost:9999/v1"


def test_llm_uses_configured_temperature(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    monkeypatch.setenv("LLM__TEMPERATURE", "0.5")
    settings = Settings()
    llm = create_llm(settings)
    assert llm.temperature == 0.5


def test_llm_uses_configured_max_tokens(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    monkeypatch.setenv("LLM__MAX_TOKENS", "2048")
    settings = Settings()
    llm = create_llm(settings)
    assert llm.max_tokens == 2048


def test_llm_uses_default_max_tokens(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    settings = Settings()
    llm = create_llm(settings)
    assert llm.max_tokens == 4096


def test_llm_uses_configured_timeout(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    monkeypatch.setenv("LLM__TIMEOUT", "120")
    settings = Settings()
    llm = create_llm(settings)
    assert llm.request_timeout == 120


def test_llm_uses_default_timeout(monkeypatch):
    monkeypatch.setenv("WCL__CLIENT_ID", "x")
    monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
    settings = Settings()
    llm = create_llm(settings)
    assert llm.request_timeout == 300
