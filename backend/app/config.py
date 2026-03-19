from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "pitwall-insights-backend"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitwall_insights"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()