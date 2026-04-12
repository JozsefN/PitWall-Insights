from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "pitwall-insights-backend"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitwall_insights"
    fastf1_cache_dir: str = ".fastf1-cache"
    session_cache_ttl_hours: int = 168
    fastf1_import_timeout: int = 180
    default_season_lookback: int = 1

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production", "false", "0", "no"}:
                return False
            if lowered in {"debug", "dev", "development", "true", "1", "yes"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
