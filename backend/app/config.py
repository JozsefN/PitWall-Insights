from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "pitwall-insights-backend"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitwall_insights"
    ingestion_source: str = "openf1"
    fastf1_cache_dir: str | None = None
    session_cache_ttl_hours: int = 168
    import_job_retention_hours: int = 168
    import_job_stale_after_minutes: int = 30
    import_job_max_attempts: int = 2
    import_worker_poll_seconds: int = 5
    fastf1_import_timeout: int = 180
    default_season_lookback: int = 1
    provider_credentials_key: SecretStr | None = None
    provider_credentials_key_file: str | None = None
    stripe_test_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_analyst_month_price: str | None = None
    stripe_analyst_year_price: str | None = None
    stripe_pro_month_price: str | None = None
    stripe_pro_year_price: str | None = None
    stripe_portal_configuration: str | None = None
    web_app_url: str = "http://localhost:5173"
    google_client_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_implicit_tls: bool = False

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
