from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "pitwall-insights-backend"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitwall_insights"
    ingestion_source: str = "fastf1"
    fastf1_cache_dir: str | None = None
    session_cache_ttl_hours: int = 168
    import_job_retention_hours: int = 168
    import_job_stale_after_minutes: int = 30
    import_job_max_attempts: int = 2
    import_worker_poll_seconds: int = 5
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

    @field_validator("fastf1_cache_dir", mode="before")
    @classmethod
    def parse_optional_path(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
