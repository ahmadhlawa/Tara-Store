"""Build a deployment package for Tara Store.

    python scripts/make_release_package.py [--output release] [--skip-build]

What it produces is a zip archive containing only the files a server needs: the backend
source, the Alembic migrations, the built frontend, the instance profile, an example
environment file and instructions.

What it deliberately does NOT contain — and refuses to build if it would:

  * `.env` or any real secret
  * SQLite databases
  * uploaded media
  * `node_modules`, virtual environments, `dist` source maps' parent tooling
  * `.git` history
  * test caches, coverage output, `__pycache__`

The allow-list below is the mechanism. Nothing is copied unless a rule names it, so a new
file added to the repository cannot silently end up in a client archive. The scan at the
end is a second, independent check on the finished tree.

IMPORTANT: this builds files only. It does not deploy or certify actual server readiness.
Production is MySQL/R2 with FastAPI/systemd behind Nginx and a built static SPA.
The shared private LibreTranslate service is external infrastructure, not packaged.

"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# (source, destination) — directories are copied whole, minus EXCLUDED_NAMES.
DIRECTORIES: list[tuple[str, str]] = [
    ("backend/app", "backend/app"),
    ("backend/alembic", "backend/alembic"),
    ("backend/scripts", "backend/scripts"),
    ("frontend/dist", "frontend/dist"),
    ("deployment/nginx", "deployment/nginx"),
    ("deployment/systemd", "deployment/systemd"),
]

FILES: list[tuple[str, str]] = [
    ("backend/alembic.ini", "backend/alembic.ini"),
    ("backend/pyproject.toml", "backend/pyproject.toml"),
    ("backend/constraints.txt", "backend/constraints.txt"),
    ("VERSION", "VERSION"),
    ("instance/tara-store.yaml", "instance/tara-store.yaml"),
    ("deployment/env/backend.env.example", "deployment/env/backend.env.example"),
    ("deployment/README.md", "deployment/README.md"),
    ("docs/deployment-templates.md", "docs/deployment-templates.md"),
    ("docs/deployment/r2-preview-setup.md", "docs/deployment/r2-preview-setup.md"),
    ("docs/deployment/libretranslate.md", "docs/deployment/libretranslate.md"),
    ("docs/backup-and-restore.md", "docs/backup-and-restore.md"),
    ("docs/future-mysql-migration.md", "docs/future-mysql-migration.md"),
    ("docs/deployment/mysql-local-development.md", "docs/deployment/mysql-local-development.md"),
    ("docs/known-limitations.md", "docs/known-limitations.md"),
    ("docs/client-data-readiness.md", "docs/client-data-readiness.md"),
    ("docs/local-setup.md", "docs/local-setup.md"),

    ("docs/template-origin.md", "docs/template-origin.md"),
]

# Pruned from every copied directory, at any depth.
EXCLUDED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    "tests",
    "tests_mysql",
    "uploads",
    "tara-uploads",
    "htmlcov",
    "generated",
    "test-results",
    "playwright-report",
    ".artifacts",
}

EXCLUDED_SUFFIXES = (
    ".db", ".sqlite", ".sqlite3", ".bak", ".dump", ".sql", ".sql.gz", ".dump.gz",
    ".sql.bz2", ".sql.xz", ".db-journal", ".db-wal", ".db-shm",
    ".sqlite-journal", ".sqlite-wal", ".sqlite-shm", ".sqlite3-journal",
    ".sqlite3-wal", ".sqlite3-shm", ".pyc", ".pyo", ".log", ".coverage", ".pem", ".key",
)

# Any file whose name matches is a build failure, not a warning.
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", "secrets.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_ed25519"}


def _keep(path: Path) -> bool:
    if path.name in FORBIDDEN_NAMES:
        return False
    # `.env.example` is intentional and carries no values; a real `.env` never is.
    if path.name.startswith(".env") and not path.name.endswith(".example"):
        return False
    return not path.name.lower().endswith(EXCLUDED_SUFFIXES) and "credentials" not in path.name.lower()


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in EXCLUDED_NAMES or not _keep(Path(directory) / name)
    }


def build_frontend() -> None:
    print("-> building the frontend")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        sys.exit("npm was not found on PATH. Install Node, or pass --skip-build.")
    result = subprocess.run([npm, "run", "build"], cwd=REPO_ROOT / "frontend")
    if result.returncode != 0:
        sys.exit("The frontend build failed. Nothing was packaged.")


def stage(destination: Path) -> None:
    for source_name, target_name in DIRECTORIES:
        source = REPO_ROOT / source_name
        if not source.is_dir():
            sys.exit(
                f"Missing {source_name}. "
                + ("Run without --skip-build." if "dist" in source_name else "")
            )
        is_static = source_name == "frontend/dist"
        if is_static and (source.is_symlink() or any(path.is_symlink() for path in source.rglob("*"))):
            sys.exit("Symlinks are not allowed in frontend/dist.")
        shutil.copytree(source, destination / target_name, ignore=_ignore, symlinks=is_static)
        if is_static:
            normalize_static_permissions(destination / target_name)

    for source_name, target_name in FILES:
        source = REPO_ROOT / source_name
        if not source.is_file():
            sys.exit(f"Missing {source_name}.")
        target = destination / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # Generate the fixed production runtime requirements, including both extras.
    requirements = _requirements_from_pyproject()
    (destination / "backend" / "requirements.txt").write_text(requirements, encoding="utf-8")

    (destination / "READ-ME-FIRST.md").write_text(_instructions(), encoding="utf-8")


def normalize_static_permissions(root: Path) -> None:
    """Give only packaged SPA content Nginx-readable modes."""
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink in static build: {path}")
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)


def _requirements_from_pyproject() -> str:
    """Read the runtime dependencies out of pyproject, so the two cannot drift."""
    import tomllib

    data = tomllib.loads((REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]
    dependencies = [dep for dep in data["project"]["dependencies"]
                    if not dep.startswith("PyMySQL")]
    dependencies += extras["mysql"] + extras["r2"]
    header = "# Generated by scripts/make_release_package.py from backend/pyproject.toml.\n"
    return header + "\n".join(sorted(dependencies)) + "\n"


def _instructions() -> str:
    return f"""# Tara Store deployment package

Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from the current working tree.

This package is not a deployment or proof of server readiness. Production uses MySQL,
R2, a static SPA and FastAPI/systemd behind Nginx. The existing shared loopback
LibreTranslate service, its models and other projects' resources are not included.

Read deployment/README.md and docs/deployment-templates.md before a separately
approved installation. Templates need placeholder substitution and host review.
Copy deployment/env/backend.env.example to private backend/.env; fill credentials
on the target. backend/requirements.txt includes MySQL authentication and R2 extras.
Install with constraints.txt. Never copy development databases/uploads or seed demos.
Back up existing MySQL/R2 data before forward Alembic migrations. Never rewrite history.
Serve frontend/dist as the SPA and proxy API/health/SEO to Tara's dedicated loopback
backend. Public media URLs come directly from R2_PUBLIC_BASE_URL; no local /media alias.
Do not recreate or manage the shared translation service from this application release.

The archive excludes real environments, databases, uploads, generated customer catalogs,
Git history, tests and installed dependencies. Source CLI tools are intentionally kept:
pyproject exposes them as entrypoints; retaining them avoids broken runtime imports.
"""


def audit(root: Path) -> list[str]:
    """Independent check on the finished tree. The allow-list should make this quiet."""
    problems = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if not _keep(path):
            problems.append(f"secret or runtime file: {relative}")
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            problems.append(f"excluded directory survived: {relative}")
    for required in ("backend/constraints.txt", "instance/tara-store.yaml", "deployment/env/backend.env.example"):
        if not (root / required).is_file():
            problems.append(f"required release file missing: {required}")
    current_docs = [root / "deployment", root / "docs/deployment-templates.md",
                    root / "READ-ME-FIRST.md"]
    for source in current_docs:
        paths = source.rglob("*") if source.is_dir() else [source]
        for path in paths:
            if path.is_file():
                text = path.read_text(encoding="utf-8").lower()
                if "vista" in text:
                    problems.append(f"stale Vista identity in current release instructions: {path.relative_to(root)}")
                if "instance/vista-store.yaml" in text:
                    problems.append(f"nonexistent Vista profile in release instructions: {path.relative_to(root)}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default="release", help="Output directory (default: release)")
    parser.add_argument(
        "--skip-build", action="store_true", help="Use the existing frontend/dist as-is."
    )
    args = parser.parse_args()

    if not args.skip_build:
        build_frontend()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    output_root = (REPO_ROOT / args.output).resolve()
    package_name = f"tara-store-e-commerce-{stamp}"
    staging = output_root / package_name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    print(f"-> staging into {staging}")
    stage(staging)

    print("-> auditing the staged tree")
    problems = audit(staging)
    if problems:
        shutil.rmtree(staging)
        print("\nRefusing to package. The staged tree contained:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    archive = output_root / f"{package_name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(staging))

    files = sum(1 for path in staging.rglob("*") if path.is_file())
    print(f"\nPackaged {files} files -> {archive}")
    print(f"  {archive.stat().st_size / 1024:.0f} KB")
    print("\nNo secrets, databases, uploads or Git history are included.")
    print("Not deployed. Review host configuration and operational readiness separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
