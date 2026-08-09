from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import APIModel, UTCDateTime

MAX_MEDIA_FILENAME_LENGTH = 300


class MediaAssetRenameIn(APIModel):
    original_filename: str = Field(min_length=1, max_length=MAX_MEDIA_FILENAME_LENGTH)

    @field_validator("original_filename")
    @classmethod
    def _safe_filename(cls, value: str) -> str:
        if not value.strip() or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("invalid filename")
        if any(ord(char) < 32 for char in value):
            raise ValueError("invalid filename")
        return value


class MediaAssetOut(APIModel):
    id: int
    original_filename: str
    stored_key: str
    content_type: str
    size_bytes: int
    url: str
    storage_provider: str
    uploaded_by_id: int | None = None
    created_at: UTCDateTime


class AuditLogOut(APIModel):
    id: int
    admin_user_id: int | None = None
    admin_email: str | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    meta: dict = {}
    created_at: UTCDateTime
