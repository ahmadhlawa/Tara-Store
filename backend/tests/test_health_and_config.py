from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_generates(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/products" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]


def test_settings_parse_cors_origins_from_a_comma_string() -> None:
    config = Settings(CORS_ORIGINS="http://a.test, http://b.test")
    assert config.CORS_ORIGINS == ["http://a.test", "http://b.test"]


def test_cors_origins_load_from_a_dotenv_file_in_the_documented_form(tmp_path: Path) -> None:
    """.env.example documents a comma-separated list; it must actually load.

    Passing the value as a keyword argument skips the dotenv source, so only a real
    file proves the documented setup works.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n",
        encoding="utf-8",
    )
    config = Settings(_env_file=env_file)
    assert config.CORS_ORIGINS == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_origins_load_from_an_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://shop.example.com,https://www.example.com")
    config = Settings(_env_file=None)
    assert config.CORS_ORIGINS == ["https://shop.example.com", "https://www.example.com"]


def test_cors_origins_also_accept_a_json_list(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('CORS_ORIGINS=["https://a.test", "https://b.test"]\n', encoding="utf-8")
    assert Settings(_env_file=env_file).CORS_ORIGINS == ["https://a.test", "https://b.test"]


def test_the_shipped_env_example_is_loadable() -> None:
    """The file we tell operators to copy must parse without editing."""
    example = Path(__file__).resolve().parents[1] / ".env.example"
    config = Settings(_env_file=example)
    assert config.CORS_ORIGINS  # parsed into a non-empty list
    assert config.APP_NAME


def test_relative_sqlite_url_is_anchored_to_the_backend_root() -> None:
    config = Settings(DATABASE_URL="sqlite+pysqlite:///./data/example.db")
    url = config.sqlalchemy_url()
    assert url.startswith("sqlite+pysqlite:///")
    assert Path(url.removeprefix("sqlite+pysqlite:///")).is_absolute()


def test_mysql_url_is_passed_through_untouched() -> None:
    mysql_url = "mysql+pymysql://user:pass@127.0.0.1:3306/db"
    assert Settings(DATABASE_URL=mysql_url).sqlalchemy_url() == mysql_url


def test_no_admin_credentials_are_shipped_as_defaults() -> None:
    config = Settings(_env_file=None)
    assert config.INITIAL_ADMIN_EMAIL == ""
    assert config.INITIAL_ADMIN_PASSWORD == ""
