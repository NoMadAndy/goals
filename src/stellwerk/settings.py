from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


_DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./data/stellwerk.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Dev default: SQLite file in ./data
    # Preprod/Prod: set to Postgres URL (see docs/deployment.md)
    database_url: str = _DEFAULT_DATABASE_URL

    # Debug UI + endpoints (SSE console)
    stellwerk_debug: bool = False

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    @field_validator("database_url", mode="before")
    @classmethod
    def _database_url_blank_to_default(cls, v):
        if v is None:
            return _DEFAULT_DATABASE_URL
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return _DEFAULT_DATABASE_URL
            if len(s) >= 2 and s[0] == s[-1] and s[0] in {"\"", "'"}:
                s = s[1:-1].strip()
            return s
        return v


settings = Settings()
