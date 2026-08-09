"""Small helpers shared by the admin routers.

These are helpers, not a generic CRUD endpoint: every route still declares its own
schema, permissions and audit action.
"""

from __future__ import annotations

from typing import Any, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], entity_id: int, message: str = "العنصر غير موجود.") -> T:
    instance = db.get(model, entity_id)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": message},
        )
    return instance


def apply_updates(instance: Any, payload: BaseModel, *, exclude: set[str] | None = None) -> list[str]:
    """Copy only the fields the caller actually sent. Returns the changed names."""
    exclude = exclude or set()
    changed: list[str] = []
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in exclude:
            continue
        if getattr(instance, field, None) != value:
            setattr(instance, field, value)
            changed.append(field)
    return changed
