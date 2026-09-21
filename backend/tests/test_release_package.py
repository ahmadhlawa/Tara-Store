"""Production packaging must include R2/MySQL and exclude client runtime data."""

import importlib.util
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import venv

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_package", ROOT / "scripts/make_release_package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def test_production_dependencies_include_both_storage_and_database_extras():
    requirements = package._requirements_from_pyproject().splitlines()
    assert any(line.startswith("boto3") for line in requirements)
    assert any(line.startswith("PyMySQL[rsa]") for line in requirements)
    assert not any(line.startswith("PyMySQL>=") for line in requirements)


def test_release_allowlist_is_current_and_excludes_generated_instance_data():
    sources = [source for source, _ in package.FILES + package.DIRECTORIES]
    assert "instance" not in sources
    assert "instance/tara-store.yaml" in sources
    assert "deployment/env/backend.env.example" in sources
    assert not any("cpanel" in source for source in sources)
    assert all((ROOT / source).exists() for source in sources if source != "frontend/dist")


@pytest.mark.parametrize("name", [
    ".env", ".env.mysql.local", "tara.db-wal", "tara.db-shm", "tara.sql.gz",
    "tara.sqlite3-journal", "r2-credentials.yaml", "private.key", "id_ed25519",
])
def test_release_rejects_sensitive_runtime_files(name):
    assert not package._keep(Path(name))


def test_production_templates_have_no_local_media_write_or_serve_path():
    nginx = (ROOT / "deployment/nginx/commerce-CLIENT_SLUG.conf.example").read_text()
    unit = (ROOT / "deployment/systemd/commerce-CLIENT_SLUG.service.example").read_text()
    env = (ROOT / "deployment/env/backend.env.example").read_text()
    assert "alias " not in nginx
    assert "ReadWritePaths=" not in unit
    for setting in ["STORAGE_PROVIDER=r2", "R2_OBJECT_PREFIX=tara-store/", "R2_REGION=auto",
                    "DATABASE_URL=mysql+pymysql://", "TRANSLATION_ENABLED=true",
                    "LIBRETRANSLATE_URL=http://127.0.0.1:5000"]:
        assert setting in env


def test_release_migration_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config()
    config.set_main_option("script_location", str(ROOT / "backend/alembic"))
    assert ScriptDirectory.from_config(config).get_current_head() == "0029_storefront_analytics"


def test_only_staged_static_content_gets_public_modes(tmp_path, monkeypatch):
    static = tmp_path / "frontend" / "dist" / "branding"
    static.mkdir(parents=True)
    logo = static / "tara-logo2.png"
    logo.write_bytes(b"image")
    secret = tmp_path / "backend" / ".env"
    secret.parent.mkdir()
    secret.write_text("private")
    os.chmod(static, 0o700)
    os.chmod(logo, 0o600)
    os.chmod(secret, 0o600)

    original_chmod = package.os.chmod
    changed = {}

    def record_chmod(path, mode):
        changed[Path(path)] = mode
        original_chmod(path, mode)

    monkeypatch.setattr(package.os, "chmod", record_chmod)
    package.normalize_static_permissions(tmp_path / "frontend" / "dist")

    assert changed[static] == 0o755
    assert changed[logo] == 0o644
    assert secret not in changed
    if os.name != "nt":
        assert stat.S_IMODE(static.stat().st_mode) == 0o755
        assert stat.S_IMODE(logo.stat().st_mode) == 0o644
        assert stat.S_IMODE(secret.stat().st_mode) == 0o600


def test_release_rejects_symlinked_frontend_dist_root(tmp_path, monkeypatch):
    source = tmp_path / "frontend" / "dist"
    source.mkdir(parents=True)
    (source / "index.html").write_text("static")
    original_is_symlink = Path.is_symlink

    def report_static_root_as_symlink(path):
        return path == source or original_is_symlink(path)

    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(package, "DIRECTORIES", [("frontend/dist", "frontend/dist")])
    monkeypatch.setattr(package, "FILES", [])
    monkeypatch.setattr(Path, "is_symlink", report_static_root_as_symlink)

    with pytest.raises(SystemExit, match="Symlinks are not allowed in frontend/dist"):
        package.stage(tmp_path / "release")


def test_release_rejects_symlink_nested_in_frontend_dist(tmp_path, monkeypatch):
    source = tmp_path / "frontend" / "dist"
    nested = source / "branding" / "logo.png"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"image")
    original_is_symlink = Path.is_symlink

    def report_nested_path_as_symlink(path):
        return path == nested or original_is_symlink(path)

    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(package, "DIRECTORIES", [("frontend/dist", "frontend/dist")])
    monkeypatch.setattr(package, "FILES", [])
    monkeypatch.setattr(Path, "is_symlink", report_nested_path_as_symlink)

    with pytest.raises(SystemExit, match="Symlinks are not allowed in frontend/dist"):
        package.stage(tmp_path / "release")


def test_wheel_installs_backend_packages_and_storefront_media_backfill_cli(tmp_path):
    wheel_dir = tmp_path / "wheels"
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheel_dir), str(ROOT / "backend")],
        check=True,
    )
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    scripts_dir = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts_dir / ("python.exe" if os.name == "nt" else "python")
    wheel = next(wheel_dir.glob("tara_store_backend-*.whl"))
    subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)], check=True)
    subprocess.run(
        [str(python), "-c", "import app.core, app.db, app.models, app.services, app.storage; import app.cli.backfill_storefront_derivatives; import app.cli.prune_analytics"],
        check=True,
        cwd=tmp_path,
    )
    subprocess.run([str(scripts_dir / "tara-storefront-media-backfill"), "--help"], check=True, cwd=tmp_path)
    subprocess.run([str(scripts_dir / "tara-analytics-prune"), "--help"], check=True, cwd=tmp_path)


def test_installed_wheel_uses_deployment_working_directory_for_runtime_configuration(tmp_path):
    """An installed package must not derive runtime paths from site-packages."""
    wheel_dir = tmp_path / "wheels"
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheel_dir), str(ROOT / "backend")],
        check=True,
    )
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    scripts_dir = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts_dir / ("python.exe" if os.name == "nt" else "python")
    wheel = next(wheel_dir.glob("tara_store_backend-*.whl"))
    subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)], check=True)

    deployment = tmp_path / "deployment" / "backend"
    deployment.mkdir(parents=True)
    deployment.joinpath(".env").write_text(
        "\n".join([
            "STORAGE_PROVIDER=r2",
            "LOCAL_MEDIA_ROOT=runtime-media",
            "R2_ENDPOINT_URL=https://r2.example.test",
            "R2_ACCESS_KEY_ID=test-access-key",
            "R2_SECRET_ACCESS_KEY=test-secret-key",
            "R2_BUCKET_NAME=test-bucket",
            "R2_PUBLIC_BASE_URL=https://media.example.test",
            "R2_OBJECT_PREFIX=test-store/",
            "",
        ]),
        encoding="utf-8",
    )
    environment_variables = os.environ.copy()
    environment_variables.pop("PYTHONPATH", None)
    probe = subprocess.run(
        [str(python), "-I", "-c", """
import json
from app.core.config import BACKEND_ROOT, settings
from app.storage import get_storage
print(json.dumps({
    "module_path": __import__("app.core.config", fromlist=["*"]).__file__,
    "backend_root": str(BACKEND_ROOT),
    "storage_provider": settings.STORAGE_PROVIDER,
    "media_root": str(settings.media_root),
    "storage_name": get_storage().name,
}))
"""],
        cwd=deployment,
        env=environment_variables,
        text=True,
        capture_output=True,
    )
    assert probe.returncode == 0, probe.stderr
    result = json.loads(probe.stdout)
    assert "site-packages" in result["module_path"]
    assert result["backend_root"] == str(deployment)
    assert result["storage_provider"] == "r2"
    assert result["storage_name"] == "r2"
    assert result["media_root"] == str(deployment / "runtime-media")
    subprocess.run(
        [str(scripts_dir / "tara-storefront-media-backfill"), "--help"],
        check=True,
        cwd=deployment,
        env=environment_variables,
    )


def test_product_home_migration_preserves_rows_and_default():
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec = importlib.util.spec_from_file_location("home_migration", ROOT / "backend/alembic/versions/0027_product_show_on_home.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)"))
        connection.execute(text("INSERT INTO products (id, name) VALUES (7, 'Existing'), (23, 'Other')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text("SELECT id, name, show_on_home FROM products ORDER BY id")).all() == [(7, 'Existing', 1), (23, 'Other', 1)]
        connection.execute(text("INSERT INTO products (id, name) VALUES (24, 'New')"))
        assert connection.execute(text("SELECT show_on_home FROM products WHERE id = 24")).scalar() == 0
    engine.dispose()
