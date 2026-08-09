"""Admin authentication. There are no customer accounts in this template."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.base import utcnow
from app.models import AdminUser
from app.schemas.auth import AdminUserOut, LoginRequest, TokenResponse
from app.services import audit as audit_service

router = APIRouter(tags=["auth"])

# One message for "no such account", "wrong password" and "deactivated" so the
# endpoint cannot be used to enumerate admins.
_INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={
        "code": "invalid_credentials",
        "message": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
    },
)


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    admin = db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == payload.email.lower())
    ).scalar_one_or_none()

    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise _INVALID_LOGIN
    if not admin.is_active:
        raise _INVALID_LOGIN

    admin.last_login_at = utcnow()
    audit_service.record(
        db, admin=admin, action="auth.login", entity_type="admin_user", entity_id=admin.id
    )
    db.commit()

    return TokenResponse(
        access_token=create_access_token(admin.id, admin.role),
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.get("/auth/me", response_model=AdminUserOut)
def me(admin: CurrentAdmin) -> AdminUser:
    return admin
