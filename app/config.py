from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "t2-mobile"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    instance_id: str = "local-dev"
    log_level: str = "INFO"

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://t2:t2@localhost:5432/t2mobile"
    redis_url: str = "redis://localhost:6379/0"

    session_cookie_name: str = "t2_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    session_cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
