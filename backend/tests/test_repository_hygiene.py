"""Runtime artefacts must never be tracked by Git.

This exists because four SQLite backups and one development database were once
committed and pushed. Each was a whole database carrying an administrator's
password hash alongside order rows with customer names, phones and addresses,
and removing them afterwards required rewriting published history.

The rules below are deliberately checked against the Git index rather than the
filesystem: a file that is merely present on disk is fine, and is what
.gitignore is for. Only a *tracked* file is a leak.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Whole-database files, in every spelling that has appeared or plausibly could.
# `.bak` matters as much as `.db`: the committed backups were named
# `vista_preview.db.20260804-051436.bak`, so a rule anchored on `.db$` missed them.
DATABASE_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".bak", ".dump", ".sql-journal")

# Real environment files. `.env.example` is the documented template and is the
# one member of this family that must stay tracked.
ENV_PATTERN = re.compile(r"(^|/)\.env(\..+)?$", re.IGNORECASE)
ENV_ALLOWED = re.compile(r"(^|/)\.env\.example$", re.IGNORECASE)

# Build output and installed dependencies.
GENERATED_PATTERN = re.compile(
    r"(^|/)(node_modules|dist|build|htmlcov|__pycache__|\.venv|\.pytest_cache)/",
    re.IGNORECASE,
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


@pytest.fixture(scope="module")
def tracked() -> list[str]:
    files = tracked_files()
    assert files, "git ls-files returned nothing; the hygiene check would pass vacuously"
    return files


def test_no_database_file_is_tracked(tracked: list[str]) -> None:
    offenders = [
        path
        for path in tracked
        if path.lower().endswith(DATABASE_SUFFIXES)
    ]
    assert not offenders, (
        "database or backup files are tracked by Git; they carry password hashes "
        f"and customer records and must be ignored instead: {offenders}"
    )


def test_no_real_environment_file_is_tracked(tracked: list[str]) -> None:
    offenders = [
        path
        for path in tracked
        if ENV_PATTERN.search(path) and not ENV_ALLOWED.search(path)
    ]
    assert not offenders, f"environment files are tracked by Git: {offenders}"


def test_no_generated_directory_is_tracked(tracked: list[str]) -> None:
    offenders = [path for path in tracked if GENERATED_PATTERN.search(path)]
    assert not offenders, f"generated directories are tracked by Git: {offenders}"


def test_the_matcher_recognises_the_files_that_actually_leaked() -> None:
    """Guard the guard.

    A hygiene rule that quietly stops matching is worse than none, so the exact
    paths that were published are asserted against the matcher directly. The
    `.db.<timestamp>.bak` shape is the one an `endswith('.db')` rule missed.
    """
    leaked = [
        "backend/data/vista_preview.20260802-192413.bak",
        "backend/data/vista_preview.db.20260804-051436.bak",
        "backend/data/vista_store_dev.20260802-192413.bak",
        "backend/data/vista_store_dev.db.20260804-051436.bak",
        "backend/data/commerce_dev.db",
    ]
    for path in leaked:
        assert path.lower().endswith(DATABASE_SUFFIXES), f"{path} would slip through"

    for path in ("backend/.env", "backend/.env.mysql.local", ".env.production"):
        assert ENV_PATTERN.search(path) and not ENV_ALLOWED.search(path), path

    # The template must remain trackable, or the repository loses its documentation.
    assert ENV_ALLOWED.search("backend/.env.example")
