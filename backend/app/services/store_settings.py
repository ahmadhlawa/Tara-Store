"""Access to the single StoreSettings row."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StoreSettings
from app.models.store import STORE_SETTINGS_DEFAULTS


def get_settings_row(db: Session) -> StoreSettings | None:
    return db.execute(select(StoreSettings).order_by(StoreSettings.id.asc())).scalars().first()


def get_or_create_settings(db: Session) -> StoreSettings:
    """Used by the admin API and the seed. Creates the row once, then reuses it."""
    row = get_settings_row(db)
    if row is None:
        row = StoreSettings(**STORE_SETTINGS_DEFAULTS)
        db.add(row)
        db.flush()
    return row


def public_settings(db: Session) -> StoreSettings:
    """Reads never write. An unconfigured instance reports the shipped defaults."""
    return get_settings_row(db) or StoreSettings(**STORE_SETTINGS_DEFAULTS)
