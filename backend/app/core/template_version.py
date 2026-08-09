"""The commerce foundation version — one authoritative source.

The version lives in the tracked `VERSION` file at the repository root. Nothing else
declares it: the CLI, the instance manifest and `InstanceMetadata` all read it from here.

This is deliberately *not* the Python distribution version in `pyproject.toml`. That one
identifies the backend package; this one identifies the template release an instance was
created from.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_ROOT

VERSION_FILENAME = "VERSION"

# Loose semver: MAJOR.MINOR.PATCH with an optional pre-release/build suffix.
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")


class TemplateVersionError(RuntimeError):
    """The template version could not be resolved or is malformed."""


def _candidate_paths() -> list[Path]:
    override = os.environ.get("TEMPLATE_VERSION_FILE")
    paths = [Path(override)] if override else []
    # Repository root (backend/..) first, then backend/ for an unusual layout.
    paths.append(BACKEND_ROOT.parent / VERSION_FILENAME)
    paths.append(BACKEND_ROOT / VERSION_FILENAME)
    return paths


def version_file() -> Path:
    for path in _candidate_paths():
        if path.is_file():
            return path
    searched = ", ".join(str(p) for p in _candidate_paths())
    raise TemplateVersionError(
        f"Commerce foundation {VERSION_FILENAME} file not found. Searched: {searched}"
    )


@lru_cache
def template_version() -> str:
    raw = version_file().read_text(encoding="utf-8").strip()
    if not raw:
        raise TemplateVersionError(f"{version_file()} is empty.")
    if not _VERSION_RE.match(raw):
        raise TemplateVersionError(
            f"{version_file()} contains {raw!r}, which is not a MAJOR.MINOR.PATCH version."
        )
    return raw
