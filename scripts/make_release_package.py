"""Build a deployment package for Vista Store.

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

IMPORTANT: a package built by this script is NOT certified deployable. Whether a FastAPI
application runs on the client's cPanel account is still an open question — see
docs/deployment/cpanel-capability-checklist.md. Do not tell the client this archive is
ready to upload until those answers come back.
"""

from __future__ import annotations

import argparse
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
    ("instance", "instance"),
    ("deployment/cpanel", "deployment/cpanel"),
]

FILES: list[tuple[str, str]] = [
    ("backend/alembic.ini", "backend/alembic.ini"),
    ("backend/pyproject.toml", "backend/pyproject.toml"),
    ("VERSION", "VERSION"),
    ("docs/deployment/cpanel-handoff.md", "docs/cpanel-handoff.md"),
    ("docs/deployment/cpanel-capability-checklist.md", "docs/cpanel-capability-checklist.md"),
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
    "vista-uploads",
    "htmlcov",
}

EXCLUDED_SUFFIXES = {".db", ".sqlite3", ".db-journal", ".pyc", ".pyo", ".log", ".coverage"}

# Any file whose name matches is a build failure, not a warning.
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", "secrets.json", "id_rsa"}


def _keep(path: Path) -> bool:
    if path.name in FORBIDDEN_NAMES:
        return False
    # `.env.example` is intentional and carries no values; a real `.env` never is.
    if path.name.startswith(".env") and not path.name.endswith(".example"):
        return False
    return path.suffix not in EXCLUDED_SUFFIXES


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in EXCLUDED_NAMES or not _keep(Path(directory) / name)
    }


def build_frontend() -> None:
    print("→ building the frontend")
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
        shutil.copytree(source, destination / target_name, ignore=_ignore)

    for source_name, target_name in FILES:
        source = REPO_ROOT / source_name
        if not source.is_file():
            sys.exit(f"Missing {source_name}.")
        target = destination / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # The server installs from a plain requirements file; cPanel's Python App UI expects
    # one and cannot read pyproject's optional-dependency groups.
    requirements = _requirements_from_pyproject()
    (destination / "backend" / "requirements.txt").write_text(requirements, encoding="utf-8")

    (destination / "READ-ME-FIRST.md").write_text(_instructions(), encoding="utf-8")


def _requirements_from_pyproject() -> str:
    """Read the runtime dependencies out of pyproject, so the two cannot drift."""
    import tomllib

    data = tomllib.loads((REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]
    # MySQL needs PyMySQL's rsa extra for caching_sha2_password, which is MySQL 8's
    # default. Without it the connection fails at authentication with a confusing error.
    dependencies = [
        "PyMySQL[rsa]>=1.1.1" if dep.startswith("PyMySQL") else dep for dep in dependencies
    ]
    header = "# Generated by scripts/make_release_package.py from backend/pyproject.toml.\n"
    return header + "\n".join(sorted(dependencies)) + "\n"


def _instructions() -> str:
    return f"""# Vista Store — deployment package

Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from branch
`feat/vista-store-initial-release`.

## Read this before uploading anything

**This package is not certified deployable.** It contains the right files, correctly
built and free of secrets. Whether they *run* on the client's cPanel account is still
unknown — see `docs/cpanel-capability-checklist.md`. If Setup Python App is missing, or
capped below Python 3.12, or the host forbids a long-lived process, this application does
not run there and no amount of uploading will change that.

## What is inside

```
backend/app/          FastAPI application
backend/alembic/      migrations — the schema of record
backend/scripts/      instance CLI, MySQL portability check
backend/requirements.txt
frontend/dist/        built storefront and admin, ready to serve as static files
instance/             the Vista Store profile (non-secret)
deployment/cpanel/    the example environment file
docs/                 handoff, capability checklist, template origin
```

## What is NOT inside, by design

No `.env`, no secret of any kind, no database, no uploaded media, no `node_modules`, no
virtual environment, no Git history, no tests and no caches.

## Order of operations

1. Answer the capability checklist. **Stop if Python 3.12+ with ASGI is unavailable.**
2. Create the MySQL database and user.
3. Extract this package into the application root — outside the document root if the host
   allows it, so the source and the `.env` are never reachable over HTTP.
4. `pip install -r backend/requirements.txt`
5. Copy `deployment/cpanel/backend.env.example` to the app root as `.env` and fill it in
   **on the server**. Generate a fresh `SECRET_KEY` there.
6. `alembic upgrade head` — **take a backup first; this is the first irreversible step.**
7. `python -m scripts.instance_cli apply --profile instance/vista-store.yaml`
8. `python -m app.initial_data --email <owner> --password <strong>`
9. Publish `frontend/dist/` to the document root.
10. Route `/api`, `/media` and `/health` to the backend process.
11. Enable AutoSSL and force HTTPS.

The store still needs its business data before it can take a real order — no delivery
area, no catalog, no phone number. See the handoff document.
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
    package_name = f"vista-store-e-commerce-{stamp}"
    staging = output_root / package_name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    print(f"→ staging into {staging}")
    stage(staging)

    print("→ auditing the staged tree")
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
    print(f"\nPackaged {files} files → {archive}")
    print(f"  {archive.stat().st_size / 1024:.0f} KB")
    print("\nNo secrets, databases, uploads or Git history are included.")
    print("NOT certified deployable: the cPanel capability checklist is still unanswered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
