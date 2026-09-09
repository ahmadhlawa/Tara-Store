"""Application settings, loaded from the environment (and an optional .env file)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
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
    PUBLIC_BASE_URL: str = ""

    SECRET_KEY: str = "development-only-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1)
    JWT_ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite+pysqlite:///./data/tara_store_dev.db"

    # NoDecode keeps pydantic-settings from JSON-decoding this inside the env/dotenv
    # source, which would reject the documented comma-separated form before the
    # validator below ever runs.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    LOGIN_RATE_LIMIT: int = Field(default=0, ge=0)
    ORDER_CREATE_RATE_LIMIT: int = Field(default=0, ge=0)
    ORDER_LOOKUP_RATE_LIMIT: int = Field(default=0, ge=0)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)
    TRUSTED_PROXY_IPS: Annotated[list[str], NoDecode] = ["127.0.0.1", "::1"]

    STORAGE_PROVIDER: str = "local"
    LOCAL_MEDIA_ROOT: str = "./data/uploads"
    LOCAL_MEDIA_BASE_URL: str = "/media"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024
    MAX_IMAGE_PIXELS: int = Field(default=40_000_000, ge=1, le=100_000_000)

    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_BASE_URL: str = ""
    R2_REGION: str = "auto"
    # Every object this application writes lives under this prefix, and it will not
    # delete anything outside it. Leave empty only for a bucket used by nothing else.
    R2_OBJECT_PREFIX: str = ""

    # Only used by the initial-admin command and the seed script. Never defaulted
    # to a usable credential, so an unconfigured instance has no admin at all.
    INITIAL_ADMIN_EMAIL: str = ""
    INITIAL_ADMIN_PASSWORD: str = ""
    INITIAL_ADMIN_NAME: str = "Store Owner"

    @field_validator("CORS_ORIGINS", "TRUSTED_PROXY_IPS", mode="before")
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

    @field_validator("PUBLIC_BASE_URL", mode="before")
    @classmethod
    def _normalize_public_base_url(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        parsed = urlsplit(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PUBLIC_BASE_URL must be an absolute HTTP(S) origin")
        if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_BASE_URL must be an origin without credentials, path, query or fragment")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        self.APP_ENV = self.APP_ENV.strip().lower()
        if self.APP_ENV != "production":
            return self
        if not self.PUBLIC_BASE_URL or not self.PUBLIC_BASE_URL.startswith("https://"):
            raise ValueError("production PUBLIC_BASE_URL must be an explicit HTTPS origin")
        secret = self.SECRET_KEY.strip()
        unsafe_secrets = {"development-only-secret-change-me", "replace-with-a-secure-random-value"}
        if len(secret) < 32 or len(set(secret)) < 12 or secret in unsafe_secrets:
            raise ValueError("production SECRET_KEY must be a unique secret of at least 32 characters")
        if not self.CORS_ORIGINS or any(
            origin == "*" or "localhost" in origin.lower() or "127.0.0.1" in origin
            or not origin.lower().startswith("https://")
            for origin in self.CORS_ORIGINS
        ):
            raise ValueError("production CORS_ORIGINS must contain only explicit HTTPS origins")
        if self.is_sqlite:
            raise ValueError("production DATABASE_URL must not use the development SQLite database")
        if self.STORAGE_PROVIDER.strip().lower() == "local":
            if not self.LOCAL_MEDIA_ROOT.strip():
                raise ValueError("production LOCAL_MEDIA_ROOT must be a non-empty media directory")
            if self.media_root == BACKEND_ROOT.resolve():
                raise ValueError("production LOCAL_MEDIA_ROOT must not resolve to the backend root")
        if not 1 <= self.ACCESS_TOKEN_EXPIRE_MINUTES <= 60:
            raise ValueError("production access tokens must expire within 60 minutes")
        self.LOGIN_RATE_LIMIT = self.LOGIN_RATE_LIMIT or 10
        self.ORDER_CREATE_RATE_LIMIT = self.ORDER_CREATE_RATE_LIMIT or 10
        self.ORDER_LOOKUP_RATE_LIMIT = self.ORDER_LOOKUP_RATE_LIMIT or 60
        return self

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
