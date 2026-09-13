"""Shared schema building blocks: base model, money/datetime encoding, pagination."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Generic, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")


def safe_resource_url(value: str | None) -> str | None:
    """Allow local media paths and credential-free HTTP(S) resources only."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return value
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError("URL must not contain whitespace or control characters")
    if value.startswith("/"):
        if value.startswith("//") or "\\" in value:
            raise ValueError("URL must be a safe local path")
        return value
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must use http, https, or a local path")
    if parsed.username or parsed.password:
        raise ValueError("URL must not contain credentials")
    return value


def safe_external_url(value: str | None) -> str | None:
    value = safe_resource_url(value)
    if value and value.startswith("/"):
        raise ValueError("URL must use http or https")
    return value


def safe_internal_path(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return value
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        raise ValueError("URL must be a safe local path")
    return value


def _iso_utc(value: datetime) -> str:
    """Always emit an explicit UTC instant; columns hold naive UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str, when_used="json")]

# Money is stored and computed as Decimal; it is emitted as a JSON number so clients
# do not have to parse strings. All arithmetic stays on the server.
Money = Annotated[
    Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")
]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class ErrorDetail(APIModel):
    code: str
    message: str


class ErrorResponse(APIModel):
    error: ErrorDetail


class MessageResponse(APIModel):
    message: str
