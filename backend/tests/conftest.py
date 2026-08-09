"""Test bootstrap.

Every test gets its own temporary SQLite file and its own media directory, so tests
never share state and never touch the development database, MySQL, R2 or the network.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.api.v1.endpoints.admin_media as admin_media
from app.core.config import settings
from app.core.enums import AdminRole, ProductType
from app.db.base import metadata_with_models
from app.db.session import build_engine, get_db
from app.main import app as fastapi_app
from app.models import AdminUser, Category, DeliveryArea, Product
from app.storage.local import LocalStorageProvider

SUPER_ADMIN_EMAIL = "super@example.com"
ADMIN_EMAIL = "admin@example.com"
TEST_PASSWORD = "TestPassw0rd!42"


@pytest.fixture()
def media_root(tmp_path: Path) -> Path:
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def session_factory(tmp_path: Path) -> Iterator[sessionmaker]:
    db_path = tmp_path / "test.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    metadata_with_models().create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    engine.dispose()


@pytest.fixture()
def db(session_factory: sessionmaker) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(session_factory: sessionmaker, media_root: Path) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # Point uploads at the per-test directory instead of backend/data/uploads.
    provider = LocalStorageProvider(media_root, "/media")
    original = admin_media.get_storage
    admin_media.get_storage = lambda: provider

    with TestClient(fastapi_app) as test_client:
        yield test_client

    admin_media.get_storage = original
    fastapi_app.dependency_overrides.clear()


# ── data helpers ─────────────────────────────────────────────────────────────
def make_admin(
    db: Session,
    *,
    email: str = ADMIN_EMAIL,
    role: str = AdminRole.ADMIN.value,
    is_active: bool = True,
    password: str = TEST_PASSWORD,
) -> AdminUser:
    from app.core.security import hash_password

    admin = AdminUser(
        email=email,
        full_name="Test Admin",
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def super_admin(db: Session) -> AdminUser:
    return make_admin(db, email=SUPER_ADMIN_EMAIL, role=AdminRole.SUPER_ADMIN.value)


@pytest.fixture()
def normal_admin(db: Session) -> AdminUser:
    return make_admin(db, email=ADMIN_EMAIL, role=AdminRole.ADMIN.value)


@pytest.fixture()
def super_token(client: TestClient, super_admin: AdminUser) -> str:
    return login(client, super_admin.email)


@pytest.fixture()
def admin_token(client: TestClient, normal_admin: AdminUser) -> str:
    return login(client, normal_admin.email)


@pytest.fixture()
def category(db: Session) -> Category:
    row = Category(name="ريزن", slug="resin", is_active=True, sort_order=0)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def make_product(
    db: Session,
    *,
    slug: str = "test-product",
    name: str = "منتج اختبار",
    price: str = "100.00",
    stock: int = 10,
    is_active: bool = True,
    track_inventory: bool = True,
    product_type: str = ProductType.STANDARD.value,
    category_id: int | None = None,
    **extra,
) -> Product:
    from app.services.catalog import refresh_search_text

    product = Product(
        name=name,
        slug=slug,
        price=Decimal(price),
        stock_quantity=stock,
        is_active=is_active,
        track_inventory=track_inventory,
        product_type=product_type,
        category_id=category_id,
        **extra,
    )
    refresh_search_text(product)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture()
def delivery_area(db: Session) -> DeliveryArea:
    area = DeliveryArea(
        name="رام الله",
        delivery_fee=Decimal("20.00"),
        free_delivery_threshold=Decimal("500.00"),
        is_active=True,
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


@pytest.fixture()
def settings_obj():
    return settings
