"""Admin authentication. There are no customer accounts in this template."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.core.rate_limit import login_rate_limit, login_ip_rate_limit, login_account_rate_limit
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
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    # Count only failed credentials. The identifier is part of the in-memory key
    # (hashed by the limiter), so a targeted brute-force cannot evade the IP limit.
    login_rate_limit.check(request, identifier=payload.email)
    login_ip_rate_limit.check(request)
    login_account_rate_limit.check(request, identifier=payload.email)
    admin = db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == payload.email.lower())
    ).scalar_one_or_none()

    password_hash = admin.password_hash if admin is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, password_hash)
    if admin is None or not password_valid:
        login_rate_limit.record_failure(request, identifier=payload.email)
        login_ip_rate_limit.record_failure(request)
        login_account_rate_limit.record_failure(request, identifier=payload.email)
        raise _INVALID_LOGIN
    if not admin.is_active:
        login_rate_limit.record_failure(request, identifier=payload.email)
        login_ip_rate_limit.record_failure(request)
        login_account_rate_limit.record_failure(request, identifier=payload.email)
        raise _INVALID_LOGIN

    login_rate_limit.clear(request, identifier=payload.email)

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
