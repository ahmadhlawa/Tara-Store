"""Maintenance mode: the public storefront closes, the owner keeps working.

The behaviour lives in `app.api.deps.require_storefront_open`, applied to the public
routers in `app/api/v1/router.py`, so this is where it is tested.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AdminUser
from app.services import store_settings as settings_service
from tests.conftest import TEST_PASSWORD, auth, make_product

PUBLIC_STOREFRONT_PATHS = [
    "/api/v1/products",
    "/api/v1/products/featured",
    "/api/v1/categories",
    "/api/v1/hero-slides",
    "/api/v1/home-sections",
    "/api/v1/delivery-areas",
]


def set_maintenance(db: Session, enabled: bool) -> None:
    row = settings_service.get_or_create_settings(db)
    row.store_name = "متجر الصيانة"
    row.phone = "0590000000"
    row.maintenance_mode = enabled
    db.commit()


def test_disabled_maintenance_leaves_the_storefront_untouched(client: TestClient, db: Session):
    set_maintenance(db, False)
    for path in PUBLIC_STOREFRONT_PATHS:
        assert client.get(path).status_code == 200, path


def test_enabled_maintenance_closes_the_public_storefront(client: TestClient, db: Session):
    set_maintenance(db, True)
    for path in PUBLIC_STOREFRONT_PATHS:
        response = client.get(path)
        assert response.status_code == 503, path
        assert response.json()["error"]["code"] == "maintenance_mode"


def test_enabled_maintenance_closes_pricing_and_checkout(client: TestClient, db: Session):
    product = make_product(db, slug="maintenance-product")
    set_maintenance(db, True)

    priced = client.post(
        "/api/v1/cart/price",
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )
    assert priced.status_code == 503
    assert priced.json()["error"]["code"] == "maintenance_mode"

    ordered = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "سارة أحمد",
            "customer_phone": "0591234567",
            "address": "رام الله، شارع الإرسال",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert ordered.status_code == 503


def test_health_and_store_identity_stay_reachable(client: TestClient, db: Session):
    set_maintenance(db, True)

    assert client.get("/health").status_code == 200

    settings_response = client.get("/api/v1/store/settings")
    assert settings_response.status_code == 200
    body = settings_response.json()
    assert body["maintenance_mode"] is True
    assert body["store_name"] == "متجر الصيانة"
    # The maintenance screen is built from this payload; it must stay non-private.
    assert "order_notifications_email" not in body
    assert "id" not in body


def test_admin_login_and_admin_apis_keep_working(
    client: TestClient, db: Session, normal_admin: AdminUser
):
    set_maintenance(db, True)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": normal_admin.email, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200
    for path in ["/api/v1/admin/dashboard", "/api/v1/admin/products", "/api/v1/admin/settings"]:
        assert client.get(path, headers=auth(token)).status_code == 200, path

    # Still closed to an unauthenticated caller, for the usual reason.
    assert client.get("/api/v1/admin/dashboard").status_code == 401


def test_the_owner_can_switch_it_back_off_from_admin(
    client: TestClient, db: Session, admin_token: str
):
    set_maintenance(db, True)
    assert client.get("/api/v1/products").status_code == 503

    response = client.patch(
        "/api/v1/admin/settings",
        json={"maintenance_mode": False},
        headers=auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["maintenance_mode"] is False

    # No restart, no rebuild: the very next public request is served again.
    assert client.get("/api/v1/products").status_code == 200


@pytest.mark.parametrize("path", ["/api/v1/store/settings", "/health"])
def test_the_gate_never_redirects(client: TestClient, db: Session, path: str):
    set_maintenance(db, True)
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 200


def test_an_instance_without_a_settings_row_is_open(client: TestClient):
    # A freshly migrated database has no store_settings row at all.
    assert client.get("/api/v1/products").status_code == 200
