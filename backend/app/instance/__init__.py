"""Instance productization: profile validation, client bootstrap and manifests."""

from __future__ import annotations

from app.instance.bootstrap import (
    InstanceConflictError,
    Plan,
    PlannedAction,
    apply_profile,
    build_plan,
)
from app.instance.manifest import build_manifest
from app.instance.profile import (
    SUPPORTED_FEATURES,
    SUPPORTED_PROFILE_SCHEMA_VERSIONS,
    InstanceProfile,
    ProfileError,
    load_profile,
    parse_profile,
)

__all__ = [
    "InstanceConflictError",
    "InstanceProfile",
    "Plan",
    "PlannedAction",
    "ProfileError",
    "SUPPORTED_FEATURES",
    "SUPPORTED_PROFILE_SCHEMA_VERSIONS",
    "apply_profile",
    "build_manifest",
    "build_plan",
    "load_profile",
    "parse_profile",
]
