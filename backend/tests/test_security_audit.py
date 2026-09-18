"""Release security matrix, adversarial inputs and bounded-query assertions."""
from datetime import datetime, timedelta, timezone
import re

import jwt
import pytest
from fastapi.routing import APIRoute
from sqlalchemy import event, select, text

from app.api.deps import get_current_admin, require_super_admin
from app.core.config import settings
from app.core import rate_limit
from app.core.security import hash_password, verify_password
from app.main import app
from app.models import Order
from tests.conftest import ADMIN_EMAIL, TEST_PASSWORD, auth, make_product


def dependencies(dependant):
    yield dependant.call
    for child in dependant.dependencies:
        yield from dependencies(child)


def registered_routes(router):
    for route in router.routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from registered_routes(included)
        elif isinstance(route, APIRoute):
            yield route


ADMIN_ROUTES = [route for route in registered_routes(app) if "/admin/" in route.path]


@pytest.mark.parametrize("route", ADMIN_ROUTES, ids=lambda route: f"{next(iter(route.methods))} {route.path}")
def test_every_admin_operation_requires_authentication(client, route):
    assert get_current_admin in set(dependencies(route.dependant))
    path = settings.API_V1_PREFIX + re.sub(r"\{[^}]+\}", "1", route.path)
    response = client.request(next(iter(route.methods)), path, json={})
    assert response.status_code == 401, (path, response.text)


def test_every_super_admin_operation_rejects_normal_role(client, admin_token):
    routes = [route for route in ADMIN_ROUTES if require_super_admin in set(dependencies(route.dependant))]
    assert routes
    for route in routes:
        path = settings.API_V1_PREFIX + re.sub(r"\{[^}]+\}", "1", route.path)
        response = client.request(next(iter(route.methods)), path, json={}, headers=auth(admin_token))
        assert response.status_code == 403, (path, response.text)


@pytest.mark.parametrize("mutation", ["missing_exp", "missing_iat", "expired", "wrong_type", "wrong_signature", "bad_sub"])
def test_jwt_claims_and_signature_are_enforced(client, normal_admin, mutation):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(normal_admin.id), "iat": now, "exp": now + timedelta(minutes=1), "type": "access"}
    key = settings.SECRET_KEY
    if mutation.startswith("missing_"):
        payload.pop(mutation.removeprefix("missing_"))
    elif mutation == "expired":
        payload["exp"] = now - timedelta(seconds=10)
    elif mutation == "wrong_type":
        payload["type"] = "refresh"
    elif mutation == "wrong_signature":
        key = "different-signing-key-with-32-characters"
    elif mutation == "bad_sub":
        payload["sub"] = "not-an-admin-id"
    token = jwt.encode(payload, key, algorithm=settings.JWT_ALGORITHM)
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401


def test_password_hash_is_argon2id_and_not_serialized(client, admin_token, normal_admin):
    assert normal_admin.password_hash.startswith("$argon2id$")
    assert verify_password(TEST_PASSWORD, normal_admin.password_hash)
    response = client.get("/api/v1/auth/me", headers=auth(admin_token))
    assert "password" not in response.text and normal_admin.password_hash not in response.text


def test_database_exceptions_do_not_log_bound_password_hashes(db):
    from sqlalchemy.exc import IntegrityError
    from uuid import uuid4
    secret = uuid4().hex
    db.execute(text("CREATE TABLE secret_probe (id INTEGER PRIMARY KEY, password_hash TEXT)"))
    db.execute(text("INSERT INTO secret_probe VALUES (1, :hash)"), {"hash": secret})
    with pytest.raises(IntegrityError) as error:
        db.execute(text("INSERT INTO secret_probe VALUES (1, :hash)"), {"hash": secret})
    import traceback
    assert secret not in "".join(traceback.format_exception(error.value))


def test_login_ip_budget_blocks_account_rotation(client):
    for i in range(3):
        response = client.post("/api/v1/auth/login", json={"email": f"rotate{i}@example.com", "password": "wrong"})
        assert response.status_code == 401
    response = client.post("/api/v1/auth/login", json={"email": "rotate3@example.com", "password": "wrong"})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_login_account_budget_blocks_ip_rotation(client, monkeypatch):
    # Simulate the already-resolved peer address; trusted-proxy parsing has its own tests.
    monkeypatch.setattr(rate_limit, "client_ip", lambda request: request.headers["x-test-peer"])
    for i in range(3):
        assert client.post("/api/v1/auth/login", headers={"x-test-peer": f"192.0.2.{i}"},
                           json={"email": "target@example.com", "password": "wrong"}).status_code == 401
    response = client.post("/api/v1/auth/login", headers={"x-test-peer": "192.0.2.99"},
                           json={"email": "target@example.com", "password": "wrong"})
    assert response.status_code == 429 and "Retry-After" in response.headers


def test_unknown_and_disabled_login_still_verify_a_hash(client, normal_admin, db, monkeypatch):
    import app.api.v1.endpoints.auth as endpoint
    calls = []
    monkeypatch.setattr(endpoint, "verify_password", lambda password, password_hash: calls.append(password_hash) or False)
    responses = [client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
                 for email in (ADMIN_EMAIL, "missing@example.com")]
    assert len(calls) == 2
    assert responses[0].json() == responses[1].json()


def test_sql_injection_search_is_data_and_pagination_is_bounded(client, db, super_token):
    make_product(db)
    response = client.get("/api/v1/admin/products", params={"q": "' OR 1=1; DROP TABLE products; --"}, headers=auth(super_token))
    assert response.status_code == 200 and response.json()["total"] == 0
    assert client.get("/api/v1/admin/products", headers=auth(super_token)).json()["total"] == 1
    for params in ({"page_size": 101}, {"page": 0}, {"page": 10001}):
        assert client.get("/api/v1/admin/orders", params=params, headers=auth(super_token)).status_code == 422


@pytest.mark.parametrize("quantity", [0, -1, 1000, "1; DROP TABLE orders"])
def test_checkout_rejects_invalid_quantity_without_orders(client, db, quantity):
    product = make_product(db)
    response = client.post("/api/v1/orders", json={
        "client_reference": "invalid-quantity", "customer_name": "Test Customer", "customer_phone": "0591234567",
        "address": "Test address", "items": [{"product_id": product.id, "quantity": quantity}],
    })
    assert response.status_code == 422
    assert db.scalars(select(Order)).all() == []


def test_coupon_injection_does_not_apply_discount(client, db):
    product = make_product(db)
    response = client.post("/api/v1/cart/price", json={
        "items": [{"product_id": product.id, "quantity": 1}], "coupon_code": "' OR 1=1 --",
    })
    assert response.status_code in (400, 404, 422)


@pytest.mark.parametrize("field", ["min_price", "max_price"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_price_filters_reject_nonfinite_numbers(client, field, value):
    assert client.get("/api/v1/products", params={field: value}).status_code == 422


def test_order_list_serialization_uses_two_queries_for_any_page(db):
    from app.api.v1.endpoints.admin_commerce import _order_list_payloads
    orders = [Order(id=i, order_number=f"TEST-{i}", public_token=f"test-{i}", customer_name="Test",
                    customer_phone="0591234567", address="Test", subtotal=1, total=1,
                    status="new", source="website", payment_method="cash_on_delivery") for i in range(1, 31)]
    db.add_all(orders)
    db.commit()
    rows = db.scalars(select(Order)).all()
    statements = []
    engine = db.get_bind()
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", record)
    try:
        payloads = _order_list_payloads(db, rows)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(statements) == 2 and len(payloads) == 30
    assert all(row["items_count"] == 0 and row["payment_status"] == "unpaid" for row in payloads)
