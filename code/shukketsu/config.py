from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WCLConfig(BaseModel):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    api_url: str = "https://www.warcraftlogs.com/api/v2/client"
    oauth_url: str = "https://www.warcraftlogs.com/oauth/token"


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    model: str = "nemotron-3-nano:30b"
    api_key: str = "ollama"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 300
    num_ctx: int = 32768


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LangfuseConfig(BaseModel):
    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "http://localhost:3000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    debug: bool = False
    log_level: str = "INFO"
    wcl: WCLConfig = WCLConfig()
    db: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
    app: AppConfig = AppConfig()
    langfuse: LangfuseConfig = LangfuseConfig()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
