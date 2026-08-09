"""Admin accounts and the audit log. Both are restricted to super_admin."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.crud import get_or_404
from app.api.deps import DbSession, PageParams, SuperAdmin
from app.core.enums import AdminRole
from app.core.security import hash_password
from app.models import AdminUser, AuditLog
from app.schemas.auth import AdminUserCreate, AdminUserOut, AdminUserUpdate
from app.schemas.common import MessageResponse, Page
from app.schemas.media import AuditLogOut
from app.services import audit as audit_service
from app.services import catalog as catalog_service
from app.services.errors import ConflictError, DomainError

router = APIRouter(prefix="/admin", tags=["admin-accounts"])


@router.get("/admins", response_model=Page[AdminUserOut])
def list_admins(db: DbSession, admin: SuperAdmin, pagination: PageParams) -> Page[AdminUserOut]:
    stmt = select(AdminUser).order_by(AdminUser.id.asc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [AdminUserOut.model_validate(row) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.post("/admins", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_admin(payload: AdminUserCreate, db: DbSession, admin: SuperAdmin):
    email = payload.email.lower()
    exists = db.execute(
        select(AdminUser.id).where(func.lower(AdminUser.email) == email)
    ).first()
    if exists is not None:
        raise ConflictError("البريد الإلكتروني مستخدم مسبقاً.", code="email_taken")

    account = AdminUser(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        is_active=payload.is_active,
    )
    db.add(account)
    db.flush()
    audit_service.record(
        db,
        admin=admin,
        action="admin.created",
        entity_type="admin_user",
        entity_id=account.id,
        meta={"email": account.email, "role": account.role},
    )
    db.commit()
    db.refresh(account)
    return account


@router.patch("/admins/{admin_id}", response_model=AdminUserOut)
def update_admin(
    admin_id: int, payload: AdminUserUpdate, db: DbSession, admin: SuperAdmin
):
    account = get_or_404(db, AdminUser, admin_id, "الحساب غير موجود.")
    data = payload.model_dump(exclude_unset=True)

    if account.id == admin.id:
        if data.get("is_active") is False:
            raise DomainError("لا يمكنك تعطيل حسابك الحالي.", code="cannot_disable_self")
        if data.get("role") and data["role"].value != AdminRole.SUPER_ADMIN.value:
            raise DomainError(
                "لا يمكنك تخفيض صلاحيات حسابك الحالي.", code="cannot_demote_self"
            )

    changed: list[str] = []
    if "password" in data and data["password"]:
        account.password_hash = hash_password(data.pop("password"))
        changed.append("password")
    data.pop("password", None)
    if data.get("role") is not None:
        data["role"] = data["role"].value
    for field, value in data.items():
        if getattr(account, field, None) != value:
            setattr(account, field, value)
            changed.append(field)

    audit_service.record(
        db,
        admin=admin,
        action="admin.updated",
        entity_type="admin_user",
        entity_id=account.id,
        meta={"fields": changed, "email": account.email},
    )
    db.commit()
    db.refresh(account)
    return account


@router.delete("/admins/{admin_id}", response_model=MessageResponse)
def delete_admin(admin_id: int, db: DbSession, admin: SuperAdmin):
    account = get_or_404(db, AdminUser, admin_id, "الحساب غير موجود.")
    if account.id == admin.id:
        raise DomainError("لا يمكنك حذف حسابك الحالي.", code="cannot_delete_self")
    remaining_supers = int(
        db.execute(
            select(func.count())
            .select_from(AdminUser)
            .where(
                AdminUser.role == AdminRole.SUPER_ADMIN.value,
                AdminUser.id != account.id,
                AdminUser.is_active.is_(True),
            )
        ).scalar_one()
    )
    if account.role == AdminRole.SUPER_ADMIN.value and remaining_supers == 0:
        raise DomainError(
            "يجب أن يبقى مدير نظام أعلى واحد على الأقل.", code="last_super_admin"
        )
    audit_service.record(
        db,
        admin=admin,
        action="admin.deleted",
        entity_type="admin_user",
        entity_id=account.id,
        meta={"email": account.email},
    )
    db.delete(account)
    db.commit()
    return MessageResponse(message="تم حذف الحساب.")


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    db: DbSession,
    admin: SuperAdmin,
    pagination: PageParams,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[AuditLogOut]:
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.id.desc())
    rows, total = catalog_service.paginate(
        db, stmt, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.build(
        [AuditLogOut.model_validate(row) for row in rows],
        total,
        pagination.page,
        pagination.page_size,
    )
