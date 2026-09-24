from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def normalize_database_url(value: str) -> str:
    """Use SQLAlchemy's psycopg 3 driver for provider-style PostgreSQL URLs."""
    for prefix in ("postgresql://", "postgres://"):
        if value.startswith(prefix):
            return f"postgresql+psycopg://{value[len(prefix):]}"
    return value


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'riverwise.sqlite3'}"
    api_cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def select_postgresql_driver(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
