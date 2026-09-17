"""Production packaging must include R2/MySQL and exclude client runtime data."""

import importlib.util
from pathlib import Path

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
    for setting in ["STORAGE_PROVIDER=r2", "R2_OBJECT_PREFIX=tara/", "R2_REGION=auto",
                    "DATABASE_URL=mysql+pymysql://", "TRANSLATION_ENABLED=true",
                    "LIBRETRANSLATE_URL=http://127.0.0.1:5000"]:
        assert setting in env
