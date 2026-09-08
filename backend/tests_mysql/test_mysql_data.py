"""Data-layer behaviour that differs between SQLite and MySQL.

SQLite is permissive: it stores Decimal as float, JSON as text, ignores VARCHAR
lengths and — unless told otherwise — does not enforce foreign keys. Everything here
exists because passing on SQLite proves none of it on MySQL.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AdminRole, ProductType
from app.core.security import hash_password
from app.models import (
    AdminUser,
    Category,
    DeliveryArea,
    HomeSection,
    Order,
    OrderItem,
    Product,
)
from app.services.catalog import refresh_search_text


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def admin_token(db: Session, client) -> str:
    email = f"{unique('mysql-admin')}@example.com"
    password = "MysqlOnlyPassw0rd!7"
    db.add(
        AdminUser(
            email=email,
            full_name="MySQL Admin",
            password_hash=hash_password(password),
            role=AdminRole.SUPER_ADMIN.value,
            is_active=True,
        )
    )
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── persistence through the real API ─────────────────────────────────────────
def test_category_and_product_persist_through_the_api(client, admin_token: str) -> None:
    name = unique("قسم")
    category = client.post(
        "/api/v1/admin/categories",
        headers=auth(admin_token),
        json={"name": name, "description": "قسم اختبار MySQL", "is_active": True},
    )
    assert category.status_code == 201, category.text
    category_id = category.json()["id"]

    product = client.post(
        "/api/v1/admin/products",
        headers=auth(admin_token),
        json={
            "name": unique("منتج"),
            "category_id": category_id,
            "sku": unique("SKU").upper(),
            "product_type": "standard",
            "price": "199.99",
            "compare_at_price": "249.50",
            "stock_quantity": 7,
            "is_active": True,
            "specifications": [{"name": "الوزن", "value": "٢ كغم", "sort_order": 0}],
        },
    )
    assert product.status_code == 201, product.text
    slug = product.json()["slug"]

    public = client.get(f"/api/v1/products/{slug}")
    assert public.status_code == 200
    body = public.json()
    assert body["category_id"] == category_id
    assert len(body["specifications"]) == 1
    # Arabic survives the utf8mb4 round trip byte for byte.
    assert body["specifications"][0]["value"] == "٢ كغم"


def test_decimal_prices_round_trip_exactly(db: Session) -> None:
    product = Product(
        name=unique("سعر"),
        slug=unique("price"),
        price=Decimal("1234.56"),
        compare_at_price=Decimal("1999.99"),
        cost_price=Decimal("0.01"),
        stock_quantity=3,
        product_type=ProductType.STANDARD.value,
    )
    refresh_search_text(product)
    db.add(product)
    db.commit()
    product_id = product.id
    db.expunge_all()

    reloaded = db.get(Product, product_id)
    assert isinstance(reloaded.price, Decimal)
    assert reloaded.price == Decimal("1234.56")
    assert reloaded.compare_at_price == Decimal("1999.99")
    assert reloaded.cost_price == Decimal("0.01")
    # NUMERIC(12,2), not a float: the classic 0.1 + 0.2 failure cannot happen.
    assert str(reloaded.price) == "1234.56"


def test_json_configuration_fields_round_trip(db: Session) -> None:
    config = {
        "limit": 8,
        "enabled": True,
        "ratio": 1.5,
        "labels": ["أول", "ثانٍ"],
        "nested": {"title": "قسم", "tags": []},
        "empty": None,
    }
    section = HomeSection(
        section_key=unique("section"),
        section_type="featured_products",
        title="قسم JSON",
        sort_order=99,
        is_visible=True,
        config=config,
    )
    db.add(section)
    db.commit()
    section_id = section.id
    db.expunge_all()

    reloaded = db.get(HomeSection, section_id)
    assert reloaded.config == config
    assert reloaded.config["nested"]["title"] == "قسم"
    assert reloaded.config["labels"] == ["أول", "ثانٍ"]


# ── constraints MySQL actually enforces ──────────────────────────────────────
def test_unique_constraints_are_enforced(db: Session) -> None:
    slug = unique("dup")

    def build() -> Product:
        product = Product(
            name="مكرر",
            slug=slug,
            price=Decimal("10.00"),
            stock_quantity=1,
            product_type=ProductType.STANDARD.value,
        )
        refresh_search_text(product)
        return product

    db.add(build())
    db.commit()

    db.add(build())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_foreign_keys_are_enforced(db: Session) -> None:
    orphan = OrderItem(
        order_id=987_654_321,
        product_name="يتيم",
        quantity=1,
        unit_price=Decimal("1.00"),
        line_total=Decimal("1.00"),
    )
    db.add(orphan)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_deleted_category_nulls_the_product_reference(db: Session) -> None:
    category = Category(name=unique("قسم"), slug=unique("cat"), is_active=True)
    db.add(category)
    db.commit()

    product = Product(
        name=unique("منتج"),
        slug=unique("prod"),
        price=Decimal("50.00"),
        stock_quantity=1,
        product_type=ProductType.STANDARD.value,
        category_id=category.id,
    )
    refresh_search_text(product)
    db.add(product)
    db.commit()
    product_id = product.id

    # Deleted through SQL, not the ORM, so this exercises InnoDB's own
    # ON DELETE SET NULL rather than SQLAlchemy nulling the child for us.
    db.execute(text("DELETE FROM categories WHERE id = :id"), {"id": category.id})
    db.commit()
    db.expunge_all()

    assert db.get(Product, product_id).category_id is None


# ── guest checkout and inventory ─────────────────────────────────────────────
def test_guest_order_creation_and_inventory_update(client, db: Session) -> None:
    area = DeliveryArea(
        name=unique("منطقة"),
        delivery_fee=Decimal("25.50"),
        free_delivery_threshold=Decimal("500.00"),
        is_active=True,
    )
    product = Product(
        name=unique("منتج طلب"),
        slug=unique("order-product"),
        price=Decimal("120.25"),
        stock_quantity=10,
        track_inventory=True,
        is_active=True,
        product_type=ProductType.STANDARD.value,
    )
    refresh_search_text(product)
    db.add_all([area, product])
    db.commit()

    response = client.post(
        "/api/v1/orders",
        json={
            "client_reference": unique("mysql-order"),
            "customer_name": "سارة أحمد",
            "customer_phone": "0591234567",
            "address": "رام الله، شارع الإرسال",
            "delivery_area_id": area.id,
            "payment_method": "cash_on_delivery",
            "items": [{"product_id": product.id, "quantity": 3}],
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()

    assert Decimal(str(order["subtotal"])) == Decimal("360.75")
    assert Decimal(str(order["delivery_fee"])) == Decimal("25.50")
    assert Decimal(str(order["total"])) == Decimal("386.25")

    product_id = product.id
    # MySQL defaults to REPEATABLE READ, so this session must leave its transaction
    # before it can see what the API's session committed.
    db.rollback()
    db.expunge_all()
    assert db.get(Product, product_id).stock_quantity == 7

    stored = db.query(Order).filter(Order.order_number == str(order["order_number"])).one()
    assert stored.total == Decimal("386.25")
    assert stored.customer_name == "سارة أحمد"
    assert len(stored.items) == 1
    assert stored.items[0].line_total == Decimal("360.75")
