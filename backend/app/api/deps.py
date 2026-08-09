"""Shared FastAPI dependencies: database session, authenticated admin, pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.enums import AdminRole
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import AdminUser
from app.services import store_settings as settings_service

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "not_authenticated", "message": "الرجاء تسجيل الدخول."},
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_admin(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AdminUser:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _UNAUTHENTICATED

    try:
        admin_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise _UNAUTHENTICATED from None

    admin = db.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        # A deactivated admin's still-valid token must stop working immediately.
        raise _UNAUTHENTICATED
    return admin


CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]


def require_super_admin(admin: CurrentAdmin) -> AdminUser:
    if admin.role != AdminRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "هذه العملية متاحة لمدير النظام الأعلى فقط.",
            },
        )
    return admin


SuperAdmin = Annotated[AdminUser, Depends(require_super_admin)]


def require_storefront_open(db: DbSession) -> None:
    """Close the public shopping surface while the owner has maintenance mode on.

    Deliberately narrow. It guards the storefront's catalog, checkout and editorial
    endpoints only — never `/health`, never `/api/v1/store/settings` (the maintenance
    screen is built from it), never authentication and never the admin surface, so the
    owner can keep working and can switch the setting back off from Admin.
    """
    row = settings_service.get_settings_row(db)
    if row is not None and row.maintenance_mode:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "maintenance_mode",
                "message": "المتجر في وضع الصيانة حالياً. نعود قريباً.",
            },
        )


StorefrontOpen = Depends(require_storefront_open)


@dataclass(slots=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


PageParams = Annotated[Pagination, Depends(pagination_params)]
