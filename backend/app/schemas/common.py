"""Shared schema building blocks: base model, money/datetime encoding, pagination."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")


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
