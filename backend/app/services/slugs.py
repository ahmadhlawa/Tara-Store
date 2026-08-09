"""Slug generation that keeps Arabic letters readable in URLs."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

_SEPARATORS = re.compile(r"[\s_/\\]+")
_DISALLOWED = re.compile(r"[^\w؀-ۿ-]+", re.UNICODE)
_DASHES = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip().lower()
    text = _SEPARATORS.sub("-", text)
    text = _DISALLOWED.sub("", text)
    text = _DASHES.sub("-", text).strip("-")
    return text


def unique_slug(db: Session, model, value: str, *, exclude_id: int | None = None) -> str:
    """Return a slug for `value` that is free on `model`, suffixing -2, -3, ... if needed."""
    base = slugify(value) or "item"
    candidate = base
    suffix = 1
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if db.execute(stmt).first() is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"
