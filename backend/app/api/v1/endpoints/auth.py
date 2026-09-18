"""Admin authentication. There are no customer accounts in this template."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.core import rate_limit
from app.db.base import utcnow
from app.models import AdminUser
from app.schemas.auth import AdminUserOut, LoginRequest, TokenResponse
from app.services import audit as audit_service
from app.services.admin_login_throttle import AdminLoginThrottleService, identifier_digest

router = APIRouter(tags=["auth"])
security_logger = logging.getLogger("tara_store.security")

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


def _cooldown(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited", "message": "\u0645\u062d\u0627\u0648\u0644\u0627\u062a \u062a\u0633\u062c\u064a\u0644 \u062f\u062e\u0648\u0644 \u0643\u062b\u064a\u0631\u0629. \u062d\u0627\u0648\u0644 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649 \u0644\u0627\u062d\u0642\u064b\u0627."},
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    source_ip = rate_limit.client_ip(request)
    identifier_hash = identifier_digest(payload.email)
    limiter = AdminLoginThrottleService(db)
    blocked = limiter.check(source_ip, payload.email)
    if blocked:
        security_logger.warning("admin_login_blocked ip=%s identifier=%s retry_after=%s", source_ip, identifier_hash[:12], blocked.retry_after)
        raise _cooldown(blocked.retry_after)
    admin = db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == payload.email.lower())
    ).scalar_one_or_none()

    password_hash = admin.password_hash if admin is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, password_hash)
    if admin is None or not password_valid:
        cooldown_minutes = limiter.record_failure(source_ip, payload.email)
        db.commit()
        security_logger.warning("admin_login_failed ip=%s identifier=%s cooldown_minutes=%s", source_ip, identifier_hash[:12], cooldown_minutes or 0)
        raise _INVALID_LOGIN
    if not admin.is_active:
        cooldown_minutes = limiter.record_failure(source_ip, payload.email)
        db.commit()
        security_logger.warning("admin_login_failed ip=%s identifier=%s cooldown_minutes=%s", source_ip, identifier_hash[:12], cooldown_minutes or 0)
        raise _INVALID_LOGIN

    limiter.clear_identifier(payload.email)

    admin.last_login_at = utcnow()
    audit_service.record(
        db, admin=admin, action="auth.login", entity_type="admin_user", entity_id=admin.id
    )
    db.commit()
    security_logger.info("admin_login_succeeded ip=%s identifier=%s", source_ip, identifier_hash[:12])

    return TokenResponse(
        access_token=create_access_token(admin.id, admin.role),
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.get("/auth/me", response_model=AdminUserOut)
def me(admin: CurrentAdmin) -> AdminUser:
    return admin
