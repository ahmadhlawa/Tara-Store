from __future__ import annotations

from pathlib import Path
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.main import create_app
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.models import Category, Product, StaticPage


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def _production_settings(**overrides) -> Settings:
    values = {
        "APP_ENV": "production",
        "SECRET_KEY": "a-production-secret-with-at-least-32-chars",
        "DATABASE_URL": "mysql+pymysql://user:pass@db/store",
        "CORS_ORIGINS": ["https://shop.example.com"],
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "PUBLIC_BASE_URL": "https://shop.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": "development-only-secret-change-me"},
        {"SECRET_KEY": "replace-with-a-secure-random-value"},
        {"SECRET_KEY": "short"},
        {"CORS_ORIGINS": ["*"]},
        {"CORS_ORIGINS": ["http://localhost:5173"]},
        {"DATABASE_URL": "sqlite+pysqlite:///./data/dev.db"},
        {"ACCESS_TOKEN_EXPIRE_MINUTES": 720},
        {"PUBLIC_BASE_URL": ""},
        {"PUBLIC_BASE_URL": "http://shop.example.com"},
        {"PUBLIC_BASE_URL": "https://shop.example.com/catalog?q=x#top"},
        {"LOCAL_MEDIA_ROOT": ""},
        {"LOCAL_MEDIA_ROOT": "."},
    ],
)
def test_production_rejects_unsafe_configuration(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _production_settings(**override)


@pytest.mark.parametrize("media_root", ["./data/uploads", "../shared/media"])
def test_production_accepts_meaningful_local_media_paths(media_root: str) -> None:
    assert _production_settings(LOCAL_MEDIA_ROOT=media_root).LOCAL_MEDIA_ROOT == media_root


def test_production_disables_api_documentation() -> None:
    config = _production_settings()
    assert config.LOGIN_RATE_LIMIT == 10
    assert config.ORDER_CREATE_RATE_LIMIT == 10
    app = create_app(config)
    with TestClient(app) as client:
        assert client.get("/api/v1/openapi.json").status_code == 404
        assert client.get("/api/v1/docs").status_code == 404


def test_public_base_url_is_normalized_without_inference() -> None:
    assert Settings(PUBLIC_BASE_URL="https://SHOP.example.com/").PUBLIC_BASE_URL == "https://shop.example.com"
    assert Settings(_env_file=None).PUBLIC_BASE_URL == ""


def test_forwarded_ip_is_only_used_for_a_trusted_proxy(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["127.0.0.1"])
    headers = [(b"x-forwarded-for", b"203.0.113.8")]
    trusted = Request({"type": "http", "client": ("127.0.0.1", 1), "headers": headers})
    untrusted = Request({"type": "http", "client": ("198.51.100.4", 1), "headers": headers})
    assert client_ip(trusted) == "203.0.113.8"
    assert client_ip(untrusted) == "198.51.100.4"


def test_request_ids_are_validated_and_returned(client: TestClient) -> None:
    accepted = client.get("/health", headers={"X-Request-ID": "edge-request-123"})
    assert accepted.headers["X-Request-ID"] == "edge-request-123"
    generated = client.get("/health", headers={"X-Request-ID": "unsafe value"})
    assert generated.headers["X-Request-ID"] != "unsafe value"
    assert len(generated.headers["X-Request-ID"]) >= 8


def test_readiness_checks_database_and_local_storage(session_factory, tmp_path: Path) -> None:
    config = Settings(STORAGE_PROVIDER="local", LOCAL_MEDIA_ROOT=str(tmp_path))
    app = create_app(config)

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        response = test_client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "ok", "storage": "local"}


def test_readiness_fails_when_database_is_unavailable(tmp_path: Path) -> None:
    config = Settings(LOCAL_MEDIA_ROOT=str(tmp_path))
    app = create_app(config)

    def broken_db():
        yield object()

    app.dependency_overrides[get_db] = broken_db
    with TestClient(app) as test_client:
        assert test_client.get("/ready").status_code == 503


def test_robots_and_sitemap_use_configured_origin_and_public_rows(
    session_factory, tmp_path: Path
) -> None:
    with session_factory() as db:
        category = Category(name="Active & Category", slug="active-category", is_active=True)
        hidden = Category(name="Hidden", slug="hidden", is_active=False)
        db.add_all([category, hidden])
        db.flush()
        db.add(Product(name="Public Product", slug="public-product", price=Decimal("12.00"), stock_quantity=1, category_id=category.id, is_active=True))
        db.add(StaticPage(title="Shipping", slug="shipping-policy", content="Published", is_published=True))
        db.commit()

    config = Settings(PUBLIC_BASE_URL="https://shop.example.com/", LOCAL_MEDIA_ROOT=str(tmp_path))
    app = create_app(config)

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        settings_body = test_client.get("/api/v1/store/settings").json()
        assert settings_body["public_base_url"] == "https://shop.example.com"
        robots = test_client.get("/robots.txt")
        assert robots.headers["content-type"].startswith("text/plain")
        assert "Sitemap: https://shop.example.com/sitemap.xml" in robots.text
        sitemap = test_client.get("/sitemap.xml")
        assert sitemap.headers["content-type"].startswith("application/xml")
        assert "https://shop.example.com/product/public-product" in sitemap.text
        assert "https://shop.example.com/category/active-category" in sitemap.text
        assert "https://shop.example.com/page/shipping-policy" in sitemap.text
        assert "/hidden" not in sitemap.text
        assert all(private not in sitemap.text for private in ("/admin", "/cart", "/checkout", "/search"))
