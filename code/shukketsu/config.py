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
    base_url: str = "http://localhost:5000/v1"
    model: str = "nemotron"
    api_key: str = "not-needed"
    temperature: float = 0.1


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
