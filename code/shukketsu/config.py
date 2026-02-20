from functools import lru_cache

from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WCLConfig(BaseModel):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    api_url: str = "https://fresh.warcraftlogs.com/api/v2/client"
    oauth_url: str = "https://fresh.warcraftlogs.com/oauth/token"


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    statement_timeout_ms: int = 30000


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    model: str = "nemotron-3-nano:30b"
    api_key: str = "ollama"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 300
    num_ctx: int = 32768


class LangfuseConfig(BaseModel):
    enabled: bool = False
    public_key: str = ""
    secret_key: SecretStr = SecretStr("")
    host: str = "http://localhost:3000"


class GuildConfig(BaseModel):
    id: int = 0  # WCL guild ID
    name: str = ""
    server_slug: str = ""
    server_region: str = "US"


class AutoIngestConfig(BaseModel):
    enabled: bool = False
    poll_interval_minutes: int = 30
    zone_ids: list[int] = []  # Empty = all zones
    with_tables: bool = True
    with_events: bool = True


class BenchmarkConfig(BaseModel):
    enabled: bool = True
    refresh_interval_days: int = 7
    max_reports_per_encounter: int = 10
    zone_ids: list[int] = []  # Empty = all zones


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    debug: bool = False
    log_level: str = "INFO"
    api_key: str = ""  # empty = auth disabled
    wcl: WCLConfig = WCLConfig()
    db: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
    langfuse: LangfuseConfig = LangfuseConfig()
    guild: GuildConfig = GuildConfig()
    auto_ingest: AutoIngestConfig = AutoIngestConfig()
    benchmark: BenchmarkConfig = BenchmarkConfig()

    @model_validator(mode="after")
    def _check_cross_field_deps(self):
        if self.auto_ingest.enabled and self.guild.id <= 0:
            raise ValueError(
                "AUTO_INGEST__ENABLED=true requires GUILD__ID to be set"
            )
        if self.langfuse.enabled:
            if not self.langfuse.public_key:
                raise ValueError(
                    "LANGFUSE__ENABLED=true requires LANGFUSE__PUBLIC_KEY"
                )
            if not self.langfuse.secret_key.get_secret_value():
                raise ValueError(
                    "LANGFUSE__ENABLED=true requires LANGFUSE__SECRET_KEY"
                )
        if self.benchmark.max_reports_per_encounter < 1:
            raise ValueError(
                "BENCHMARK__MAX_REPORTS_PER_ENCOUNTER must be >= 1"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
