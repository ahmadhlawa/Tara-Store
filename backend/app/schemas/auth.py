from __future__ import annotations

from pydantic import EmailStr, Field

from app.core.enums import AdminRole
from app.schemas.common import APIModel, UTCDateTime


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class AdminUserOut(APIModel):
    """Never carries password_hash — the field simply does not exist here."""

    id: int
    email: EmailStr
    full_name: str
    role: AdminRole
    is_active: bool
    last_login_at: UTCDateTime | None = None
    created_at: UTCDateTime


class AdminUserCreate(APIModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=10, max_length=200)
    role: AdminRole = AdminRole.ADMIN
    is_active: bool = True


class AdminUserUpdate(APIModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=10, max_length=200)
    role: AdminRole | None = None
    is_active: bool | None = None
