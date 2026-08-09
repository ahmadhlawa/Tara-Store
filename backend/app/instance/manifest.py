"""Non-secret instance manifest.

Everything here is safe to commit, attach to a ticket or hand to a client. Nothing reads
`settings.SECRET_KEY`, `DATABASE_URL` or any credential — see `test_instance_cli.py`,
which asserts that.
"""

from __future__ import annotations

from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_ROOT
from app.core.template_version import template_version
from app.models import InstanceMetadata


def current_alembic_revision(db: Session) -> str | None:
    """The revision stamped in this database, or None if never migrated."""
    context = MigrationContext.configure(db.connection())
    return context.get_current_revision()


def head_alembic_revision() -> str | None:
    """The newest revision this checkout ships, read from the migration scripts."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    try:
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception:  # pragma: no cover - only when the scripts are unreadable
        return None


def build_manifest(db: Session) -> dict[str, Any]:
    metadata = db.execute(select(InstanceMetadata).limit(1)).scalar_one_or_none()
    current = current_alembic_revision(db)

    manifest: dict[str, Any] = {
        "template_version": template_version(),
        "alembic_revision": current,
        "alembic_head": head_alembic_revision(),
        "initialized": metadata is not None,
    }

    if metadata is None:
        manifest.update(
            {
                "instance_slug": None,
                "profile_schema_version": None,
                "enabled_features": [],
                "initialized_at": None,
                "last_bootstrap_at": None,
                "template_version_at_init": None,
                "profile_hash": None,
            }
        )
        return manifest

    manifest.update(
        {
            "instance_slug": metadata.instance_slug,
            "profile_schema_version": metadata.profile_schema_version,
            "enabled_features": list(metadata.enabled_features or []),
            "initialized_at": metadata.initialized_at.isoformat() + "Z",
            "last_bootstrap_at": metadata.last_bootstrap_at.isoformat() + "Z",
            "template_version_at_init": metadata.template_version,
            "profile_hash": metadata.profile_hash,
        }
    )
    return manifest
