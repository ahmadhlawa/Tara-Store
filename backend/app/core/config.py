"""Application settings, loaded from the environment (and an optional .env file)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_ENV: str = "development"
    APP_NAME: str = "Tara Store"
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "development-only-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    JWT_ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite+pysqlite:///./data/tara_store_dev.db"

    # NoDecode keeps pydantic-settings from JSON-decoding this inside the env/dotenv
    # source, which would reject the documented comma-separated form before the
    # validator below ever runs.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    STORAGE_PROVIDER: str = "local"
    LOCAL_MEDIA_ROOT: str = "./data/uploads"
    LOCAL_MEDIA_BASE_URL: str = "/media"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_BASE_URL: str = ""
    # Every object this application writes lives under this prefix, and it will not
    # delete anything outside it. Leave empty only for a bucket used by nothing else.
    R2_OBJECT_PREFIX: str = ""

    # Only used by the initial-admin command and the seed script. Never defaulted
    # to a usable credential, so an unconfigured instance has no admin at all.
    INITIAL_ADMIN_EMAIL: str = ""
    INITIAL_ADMIN_PASSWORD: str = ""
    INITIAL_ADMIN_NAME: str = "Store Owner"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept the documented comma-separated form, and a JSON list as a courtesy."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    def resolve_path(self, value: str) -> Path:
        """Resolve a possibly relative configured path against the backend root."""
        path = Path(value)
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @property
    def media_root(self) -> Path:
        return self.resolve_path(self.LOCAL_MEDIA_ROOT)

    def sqlalchemy_url(self) -> str:
        """Relative SQLite paths are anchored to the backend root, not the CWD."""
        prefix = "sqlite+pysqlite:///"
        if self.DATABASE_URL.startswith(prefix):
            raw = self.DATABASE_URL[len(prefix) :]
            if raw and not raw.startswith("/") and not Path(raw).is_absolute():
                return prefix + str(self.resolve_path(raw)).replace("\\", "/")
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
