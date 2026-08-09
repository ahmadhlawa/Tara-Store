"""Resolving a Media Library file by the name the owner uploaded it under.

A client catalog references its pictures by filename — `VST-1001-01.jpg` — and never by
URL, storage key or local path, so the same spreadsheet is valid whether the bytes end up
in the local uploads directory or in object storage.

The rules are deliberately unforgiving, because the alternative to failing is importing a
catalog where a product silently shows somebody else's picture:

* exactly one match, compared case-sensitively against `MediaAsset.original_filename`;
* no match is an error;
* more than one match is an error — the tool never picks between duplicates.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaAsset


class MediaResolutionError(LookupError):
    """A referenced filename does not resolve to exactly one Media Library asset."""


def find_by_filename(db: Session, filename: str) -> list[MediaAsset]:
    """Every asset uploaded under this exact name, oldest first.

    The comparison is done in Python: `LIKE` is case-insensitive on MySQL's default
    collation, which would make `vst-1001-01.jpg` and `VST-1001-01.jpg` the same file on
    one database and two files on another.
    """
    candidates = db.execute(
        select(MediaAsset).where(MediaAsset.original_filename == filename).order_by(MediaAsset.id)
    ).scalars()
    return [asset for asset in candidates if asset.original_filename == filename]


def resolve_one(db: Session, filename: str) -> MediaAsset:
    matches = find_by_filename(db, filename)
    if not matches:
        raise MediaResolutionError(f"{filename!r} was not found in the Media Library")
    if len(matches) > 1:
        raise MediaResolutionError(
            f"{filename!r} matches {len(matches)} Media Library files "
            f"(ids {', '.join(str(asset.id) for asset in matches)}); "
            "remove the duplicates or rename them so the reference is unambiguous"
        )
    return matches[0]


def resolve_many(db: Session, filenames: Iterable[str]) -> tuple[dict[str, MediaAsset], dict[str, str]]:
    """Resolve a batch of filenames. Returns (resolved, errors-by-filename)."""
    resolved: dict[str, MediaAsset] = {}
    errors: dict[str, str] = {}
    for filename in dict.fromkeys(filenames):
        try:
            resolved[filename] = resolve_one(db, filename)
        except MediaResolutionError as exc:
            errors[filename] = str(exc)
    return resolved, errors
