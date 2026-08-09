"""Audit trail for important admin changes."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog

_REDACTED_KEYS = {
    "password",
    "new_password",
    "current_password",
    "password_hash",
    "token",
    "access_token",
    "secret",
}


def _safe_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Keep the metadata concise and never let a credential reach the log."""
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for key, value in meta.items():
        if key.lower() in _REDACTED_KEYS:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value[:200] if isinstance(value, str) else value
        elif isinstance(value, (list, tuple)):
            out[key] = [str(v)[:80] for v in value[:20]]
        else:
            out[key] = str(value)[:200]
    return out


def record(
    db: Session,
    *,
    admin: AdminUser | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        admin_user_id=admin.id if admin else None,
        admin_email=admin.email if admin else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta=_safe_meta(meta),
    )
    db.add(entry)
    return entry
