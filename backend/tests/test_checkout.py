from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints import public_checkout
from app.core.enums import DiscountType, OrderStatus
from app.db.base import utcnow
from app.models import (
    Coupon,
    DeliveryArea,
    Order,
    PackageItem,
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
)
from app.schemas.orders import OrderCreate
from app.services import orders as orders_service
from app.services import pricing
from app.services.errors import DomainError
from tests.conftest import auth, make_product


def _coupon(db: Session, **kwargs) -> Coupon:
    defaults = {
        "code": "SAVE",
        "discount_type": DiscountType.PERCENTAGE.value,
        "discount_value": Decimal("10"),
        "min_order_amount": Decimal("0"),
        "is_active": True,
    }
    defaults.update(kwargs)
    coupon = Coupon(**defaults)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


def _order_payload(product: Product, **overrides) -> dict:
    payload = {
        "client_reference": f"test-order-{product.id}",
        "customer_name": "سارة أحمد",
        "customer_phone": "0591234567",
        "address": "رام الله، شارع الإرسال، بناية ٥",
        "items": [{"product_id": product.id, "quantity": 2}],
    }
    payload.update(overrides)
    return payload


def test_package_order_snapshots_components_and_reserves_package_and_component_stock(
    client: TestClient, db: Session
) -> None:
    """A package is one priced line, while its fulfillment contents are immutable metadata."""
    component_a = make_product(db, slug="component-a", name="Component A", stock=0)
    component_b = make_product(db, slug="component-b", name="Component B", stock=0)
    package = make_product(
        db,
        slug="package-integrity",
        name="Package Integrity",
        price="150.00",
        stock=10,
        product_type="package",
    )
    db.add_all(
        [
            PackageItem(package_product_id=package.id, included_product_id=component_a.id, quantity=2),
            PackageItem(package_product_id=package.id, included_product_id=component_b.id, quantity=1),
        ]
    )
    db.commit()

    response = client.post(
        "/api/v1/orders",
        json=_order_payload(package, items=[{"product_id": package.id, "quantity": 3}]),
    )

    assert response.status_code == 201, response.text
    order = db.get(Order, response.json()["id"])
    assert len(order.items) == 1
    assert order.items[0].quantity == 3
    assert order.items[0].unit_price == Decimal("150.00")
    components = {item.product_name: item for item in order.items[0].package_components}
    assert components["Component A"].quantity_per_package == 2
    assert components["Component A"].package_quantity == 3
    assert components["Component A"].total_quantity == 6
    assert components["Component B"].total_quantity == 3
    db.expire_all()
    assert db.get(Product, package.id).stock_quantity == 7
    assert db.get(Product, component_a.id).stock_quantity == 0
    assert db.get(Product, component_b.id).stock_quantity == 0


def test_direct_item_stock_is_independent_of_package_components(client: TestClient, db: Session) -> None:
    component = make_product(db, slug="shared-component", stock=8)
    package = make_product(db, slug="shared-package", stock=5, product_type="package")
    db.add(PackageItem(package_product_id=package.id, included_product_id=component.id, quantity=2))
    db.commit()
    response = client.post("/api/v1/orders", json=_order_payload(package, items=[
        {"product_id": component.id, "quantity": 2}, {"product_id": package.id, "quantity": 3},
    ], client_reference="direct-package-stock"))
    assert response.status_code == 201, response.text
    db.expire_all()
    assert db.get(Product, component.id).stock_quantity == 6
    assert db.get(Product, package.id).stock_quantity == 2
    order = db.get(Order, response.json()["id"])
    assert order.items[1].package_components[0].total_quantity == 6


def test_packages_sharing_a_component_do_not_consume_component_stock(client: TestClient, db: Session) -> None:
    component = make_product(db, slug="shared", stock=0)
    first = make_product(db, slug="package-a", stock=4, product_type="package")
    second = make_product(db, slug="package-b", stock=3, product_type="package")
    db.add_all([
        PackageItem(package_product_id=first.id, included_product_id=component.id, quantity=1),
        PackageItem(package_product_id=second.id, included_product_id=component.id, quantity=2),
    ])
    db.commit()
    response = client.post("/api/v1/orders", json=_order_payload(first, items=[
        {"product_id": first.id, "quantity": 2}, {"product_id": second.id, "quantity": 1},
    ], client_reference="two-packages-shared"))
    assert response.status_code == 201, response.text
    db.expire_all()
    assert db.get(Product, component.id).stock_quantity == 0
    assert db.get(Product, first.id).stock_quantity == 2
    assert db.get(Product, second.id).stock_quantity == 2


def test_package_cancellation_restores_only_package_stock_once(client: TestClient, db: Session, admin_token: str) -> None:
    component = make_product(db, slug="cancel-component", stock=0)
    package = make_product(db, slug="cancel-package", stock=2, product_type="package")
    db.add(PackageItem(package_product_id=package.id, included_product_id=component.id, quantity=2))
    db.commit()
    created = client.post("/api/v1/orders", json=_order_payload(package, items=[{"product_id": package.id, "quantity": 2}], client_reference="cancel-package-stock"))
    order = db.get(Order, created.json()["id"])
    for _ in range(2):
        response = client.post(f"/api/v1/admin/orders/{order.id}/status", headers=auth(admin_token), json={"status": "cancelled"})
        assert response.status_code == 200
    db.expire_all()
    assert db.get(Product, package.id).stock_quantity == 2
    assert db.get(Product, component.id).stock_quantity == 0


def test_variant_and_generic_package_components_are_snapshotted_without_stock_gates(client: TestClient, db: Session) -> None:
    from app.models import ProductVariant
    component = make_product(db, slug="variant-component", stock=0)
    variant = ProductVariant(product_id=component.id, title="Lavender", sku="LAV", stock_quantity=0)
    generic = make_product(db, slug="generic-component", stock=0)
    generic_variant = ProductVariant(product_id=generic.id, title="Small", stock_quantity=0)
    package = make_product(db, slug="variant-package", stock=2, product_type="package")
    db.add_all([
        variant, generic_variant, PackageItem(package_product_id=package.id, included_product_id=component.id, included_variant=variant, quantity=1),
        PackageItem(package_product_id=package.id, included_product_id=generic.id, quantity=1),
    ])
    db.commit()
    response = client.post("/api/v1/orders", json=_order_payload(package, items=[{"product_id": package.id, "quantity": 1}], client_reference="variant-package-snapshot"))
    assert response.status_code == 201, response.text
    db.expire_all()
    snapshots = db.get(Order, response.json()["id"]).items[0].package_components
    assert {(row.source_variant_id, row.variant_description, row.sku) for row in snapshots} == {(variant.id, "Lavender", "LAV"), (None, None, None)}
    assert db.get(ProductVariant, variant.id).stock_quantity == 0


def test_package_order_failure_after_snapshot_preparation_rolls_back_stock_and_rows(db: Session, monkeypatch) -> None:
    component = make_product(db, slug="rollback-component", stock=0)
    direct = make_product(db, slug="rollback-direct", stock=5)
    package = make_product(db, slug="rollback-package", stock=3, product_type="package")
    db.add(PackageItem(package_product_id=package.id, included_product_id=component.id, quantity=2))
    db.commit()

    def fail_activity(*_args, **_kwargs):
        raise RuntimeError("controlled post-snapshot failure")

    monkeypatch.setattr(orders_service, "record_order_activity", fail_activity)
    with pytest.raises(RuntimeError, match="controlled post-snapshot failure"):
        orders_service.create_order(db, orders_service.OrderDraft(
            client_reference="rollback-package-order",
            customer_name="Rollback Customer",
            customer_phone="0591234567",
            address="Rollback Address",
            items=[(direct.id, None, 2), (package.id, None, 2)],
        ))
    db.rollback()
    db.expire_all()
    assert db.query(Order).count() == 0
    assert db.get(Product, direct.id).stock_quantity == 5
    assert db.get(Product, package.id).stock_quantity == 3
    assert db.get(Product, component.id).stock_quantity == 0


# ── coupons ──────────────────────────────────────────────────────────────────
def test_percentage_coupon_is_computed_on_the_server(client: TestClient, db: Session) -> None:
    _coupon(db, code="TEN", discount_value=Decimal("10"))
    response = client.post(
        "/api/v1/coupons/validate", json={"code": "ten", "subtotal": 250}
    )
    assert response.status_code == 200
    assert response.json()["discount"] == 25.0


def test_percentage_coupon_respects_its_cap(client: TestClient, db: Session) -> None:
    _coupon(db, code="CAP", discount_value=Decimal("50"), max_discount_amount=Decimal("30"))
    response = client.post("/api/v1/coupons/validate", json={"code": "CAP", "subtotal": 400})
    assert response.json()["discount"] == 30.0


def test_fixed_coupon_is_computed_on_the_server(client: TestClient, db: Session) -> None:
    _coupon(db, code="FLAT", discount_type=DiscountType.FIXED.value, discount_value=Decimal("25"))
    response = client.post("/api/v1/coupons/validate", json={"code": "FLAT", "subtotal": 250})
    assert response.json()["discount"] == 25.0


def test_fixed_coupon_never_exceeds_the_subtotal(db: Session) -> None:
    coupon = _coupon(
        db, code="BIG", discount_type=DiscountType.FIXED.value, discount_value=Decimal("500")
    )
    assert pricing.compute_discount(coupon, Decimal("120.00")) == Decimal("120.00")


def test_expired_and_inactive_coupons_are_rejected(client: TestClient, db: Session) -> None:
    _coupon(db, code="OLD", ends_at=utcnow() - timedelta(days=1))
    _coupon(db, code="OFF", is_active=False)
    _coupon(db, code="SOON", starts_at=utcnow() + timedelta(days=1))
    _coupon(db, code="USED", usage_limit=1, used_count=1)
    _coupon(db, code="MIN", min_order_amount=Decimal("500"))

    cases = {
        "OLD": "coupon_expired",
        "OFF": "coupon_invalid",
        "SOON": "coupon_not_started",
        "USED": "coupon_exhausted",
        "MIN": "coupon_min_order",
        "NOPE": "coupon_invalid",
    }
    for code, expected in cases.items():
        response = client.post(
            "/api/v1/coupons/validate", json={"code": code, "subtotal": 100}
        )
        assert response.status_code == 400, code
        assert response.json()["error"]["code"] == expected, code


# ── delivery ─────────────────────────────────────────────────────────────────
def test_delivery_fee_applies_and_becomes_free_over_the_threshold(
    db: Session, delivery_area: DeliveryArea
) -> None:
    assert pricing.compute_delivery_fee(delivery_area, Decimal("100.00")) == Decimal("20.00")
    assert pricing.compute_delivery_fee(delivery_area, Decimal("500.00")) == Decimal("0.00")


def test_an_order_at_the_threshold_is_delivered_free(
    client: TestClient, db: Session, delivery_area: DeliveryArea
) -> None:
    """The client's rule, end to end: the stored order pays no delivery at the threshold.

    Charged from the area's own threshold, so the three areas the client gave —
    220 for الضفة and القدس, 400 for الداخل — need no code of their own. The
    boundary itself is the case worth pinning: "220 or more" is free, not "over 220".
    """
    delivery_area.delivery_fee = Decimal("25.00")
    delivery_area.free_delivery_threshold = Decimal("220.00")
    db.commit()

    product = make_product(db, price="110.00", stock=10)  # 2 × 110 == exactly 220
    response = client.post(
        "/api/v1/orders", json=_order_payload(product, delivery_area_id=delivery_area.id)
    )
    assert response.status_code == 201
    order = db.get(Order, response.json()["id"])
    assert order.subtotal == Decimal("220.00")
    assert order.delivery_fee == Decimal("0.00")
    assert order.total == Decimal("220.00")

    # A shekel short and the fee is charged again.
    cheaper = make_product(db, slug="test-product-cheaper", price="109.50", stock=10)
    response = client.post(
        "/api/v1/orders",
        json={
            **_order_payload(cheaper, delivery_area_id=delivery_area.id),
            "client_reference": "test-order-below-threshold",
        },
    )
    assert response.status_code == 201
    order = db.get(Order, response.json()["id"])
    assert order.subtotal == Decimal("219.00")
    assert order.delivery_fee == Decimal("25.00")
    assert order.total == Decimal("244.00")


def test_inactive_delivery_area_cannot_be_selected(
    client: TestClient, db: Session, delivery_area: DeliveryArea
) -> None:
    delivery_area.is_active = False
    db.commit()
    product = make_product(db, price="100.00", stock=5)
    response = client.post(
        "/api/v1/orders", json=_order_payload(product, delivery_area_id=delivery_area.id)
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "delivery_area_inactive"


# ── totals ───────────────────────────────────────────────────────────────────
def test_order_total_is_subtotal_minus_discount_plus_delivery(
    client: TestClient, db: Session, delivery_area: DeliveryArea
) -> None:
    product = make_product(db, price="100.00", stock=10)
    _coupon(db, code="TEN", discount_value=Decimal("10"))

    response = client.post(
        "/api/v1/orders",
        json=_order_payload(
            product, delivery_area_id=delivery_area.id, coupon_code="TEN"
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subtotal"] == 200.0
    assert body["discount"] == 20.0
    assert body["delivery_fee"] == 20.0
    assert body["total"] == 200.0


def test_the_server_ignores_client_supplied_prices(
    client: TestClient, db: Session
) -> None:
    product = make_product(db, price="100.00", stock=10)
    payload = _order_payload(product)
    payload["items"][0]["unit_price"] = 1  # not part of the schema
    payload["total"] = 1

    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 201
    assert response.json()["total"] == 200.0


def test_compare_at_price_is_never_charged(client: TestClient, db: Session) -> None:
    product = make_product(db, price="80.00", stock=5, compare_at_price=Decimal("120.00"))
    response = client.post(
        "/api/v1/orders", json=_order_payload(product, items=[{"product_id": product.id, "quantity": 1}])
    )
    assert response.json()["subtotal"] == 80.0


def test_variant_price_override_is_used(client: TestClient, db: Session) -> None:
    from app.models import ProductVariant

    product = make_product(db, price="100.00", stock=10)
    variant = ProductVariant(
        product_id=product.id,
        title="كبير",
        price_override=Decimal("150.00"),
        stock_quantity=5,
    )
    db.add(variant)
    db.commit()

    response = client.post(
        "/api/v1/orders",
        json=_order_payload(
            product, items=[{"product_id": product.id, "variant_id": variant.id, "quantity": 1}]
        ),
    )
    assert response.status_code == 201
    assert response.json()["subtotal"] == 150.0
    assert response.json()["items"][0]["variant_description"] == "كبير"


def test_configurable_product_requires_variant_and_snapshots_arabic_labels(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="arabic-options", name="شمعة لافندر", price="100.00")
    scent = ProductOption(product_id=product.id, name="الرائحة", sort_order=0)
    scent.values.append(ProductOptionValue(value="فراولة", sort_order=0))
    size = ProductOption(product_id=product.id, name="الحجم", sort_order=1)
    size.values.append(ProductOptionValue(value="كبير", sort_order=0))
    db.add_all([scent, size])
    db.flush()
    variant = ProductVariant(
        product_id=product.id,
        title="فراولة / كبير",
        price_override=Decimal("125.00"),
        stock_quantity=5,
        option_values=[scent.values[0], size.values[0]],
    )
    db.add(variant)
    db.commit()

    missing = client.post("/api/v1/orders", json=_order_payload(product))
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "variant_required"

    created = client.post(
        "/api/v1/orders",
        json=_order_payload(
            product,
            items=[{"product_id": product.id, "variant_id": variant.id, "quantity": 1}],
        ),
    )
    assert created.status_code == 201, created.text
    item = created.json()["items"][0]
    assert item["unit_price"] == 125
    assert item["variant_description"] == "الرائحة: فراولة، الحجم: كبير"

    scent.values[0].value = "مسك"
    db.commit()
    lookup = client.get(
        f"/api/v1/orders/{created.json()['order_number']}",
        headers={"X-Order-Token": created.json()["public_token"]},
    )
    assert lookup.json()["items"][0]["variant_description"] == "الرائحة: فراولة، الحجم: كبير"

    order = db.query(Order).filter_by(order_number=created.json()["order_number"]).one()
    completed = client.post(
        f"/api/v1/admin/orders/{order.id}/complete",
        json={"payment_method": "cash_on_delivery"},
        headers=auth(admin_token),
    )
    assert completed.status_code == 200, completed.text
    invoice_number = completed.json()["invoice"]["invoice_number"]
    invoice = client.get(
        f"/api/v1/admin/invoices/{invoice_number}", headers=auth(admin_token)
    ).json()
    assert invoice["items"][0]["variant_description"] == "الرائحة: فراولة، الحجم: كبير"


def test_a_variant_from_another_product_is_rejected(client: TestClient, db: Session) -> None:
    from app.models import ProductVariant

    product = make_product(db, slug="a", name="أ", stock=5)
    other = make_product(db, slug="b", name="ب", stock=5)
    variant = ProductVariant(product_id=other.id, title="خيار", stock_quantity=5)
    db.add(variant)
    db.commit()

    response = client.post(
        "/api/v1/orders",
        json=_order_payload(
            product, items=[{"product_id": product.id, "variant_id": variant.id, "quantity": 1}]
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "variant_mismatch"


# ── inventory ────────────────────────────────────────────────────────────────
def test_out_of_stock_product_cannot_be_ordered(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=0)
    response = client.post(
        "/api/v1/orders", json=_order_payload(product, items=[{"product_id": product.id, "quantity": 1}])
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_inactive_product_cannot_be_ordered(client: TestClient, db: Session) -> None:
    product = make_product(db, is_active=False, stock=10)
    response = client.post("/api/v1/orders", json=_order_payload(product))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "product_inactive"


def test_untracked_inventory_is_always_orderable(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=0, track_inventory=False)
    response = client.post("/api/v1/orders", json=_order_payload(product))
    assert response.status_code == 201


def test_placing_an_order_decrements_inventory_once(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=10)
    response = client.post("/api/v1/orders", json=_order_payload(product))
    assert response.status_code == 201

    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 8


def test_coupon_usage_is_counted_once_per_order(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=10, price="100.00")
    coupon = _coupon(db, code="TEN")
    client.post("/api/v1/orders", json=_order_payload(product, coupon_code="TEN"))

    db.expire_all()
    assert db.get(Coupon, coupon.id).used_count == 1


def test_cancelling_restores_stock_exactly_once(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, stock=10)
    created = client.post("/api/v1/orders", json=_order_payload(product))
    order_number = created.json()["order_number"]

    db.expire_all()
    order = db.query(Order).filter(Order.order_number == order_number).one()
    assert db.get(Product, product.id).stock_quantity == 8

    first = client.post(
        f"/api/v1/admin/orders/{order.id}/status",
        headers=auth(admin_token),
        json={"status": "cancelled", "note": "طلب ملغى"},
    )
    assert first.status_code == 200
    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 10

    # Same status again: idempotent, no second restock.
    again = client.post(
        f"/api/v1/admin/orders/{order.id}/status",
        headers=auth(admin_token),
        json={"status": "cancelled"},
    )
    assert again.status_code == 200
    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 10

    # And a cancelled order cannot be moved back into a stock-holding status.
    reopened = client.post(
        f"/api/v1/admin/orders/{order.id}/status",
        headers=auth(admin_token),
        json={"status": "processing"},
    )
    assert reopened.status_code == 422
    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 10


def test_order_status_history_is_recorded(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, stock=10)
    created = client.post("/api/v1/orders", json=_order_payload(product))
    order = db.query(Order).filter(Order.order_number == created.json()["order_number"]).one()

    client.post(
        f"/api/v1/admin/orders/{order.id}/status",
        headers=auth(admin_token),
        json={"status": "confirmed", "note": "تم التأكيد هاتفياً"},
    )
    detail = client.get(f"/api/v1/admin/orders/{order.id}", headers=auth(admin_token)).json()

    history = detail["status_history"]
    assert [h["new_status"] for h in history] == ["new", "confirmed"]
    assert history[0]["old_status"] is None
    assert history[1]["old_status"] == "new"
    assert history[1]["note"] == "تم التأكيد هاتفياً"
    assert history[1]["admin_user_id"] is not None


def test_order_items_are_snapshots(client: TestClient, db: Session, admin_token: str) -> None:
    product = make_product(db, name="الاسم الأصلي", price="100.00", stock=10)
    created = client.post("/api/v1/orders", json=_order_payload(product))
    order_id = db.query(Order).filter(
        Order.order_number == created.json()["order_number"]
    ).one().id

    client.patch(
        f"/api/v1/admin/products/{product.id}",
        headers=auth(admin_token),
        json={"name": "اسم جديد", "price": 500, "is_active": False},
    )

    detail = client.get(f"/api/v1/admin/orders/{order_id}", headers=auth(admin_token)).json()
    assert detail["items"][0]["product_name"] == "الاسم الأصلي"
    assert detail["items"][0]["unit_price"] == 100.0


def test_empty_and_invalid_carts_are_rejected(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=5)
    empty = client.post("/api/v1/orders", json=_order_payload(product, items=[]))
    assert empty.status_code == 422

    unknown = client.post(
        "/api/v1/orders", json=_order_payload(product, items=[{"product_id": 9999, "quantity": 1}])
    )
    assert unknown.status_code == 404

    bad_phone = client.post(
        "/api/v1/orders", json=_order_payload(product, customer_phone="abc")
    )
    assert bad_phone.status_code == 422


def test_rejected_checkout_does_not_persist_a_partial_order(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=5)

    response = client.post(
        "/api/v1/orders",
        json=_order_payload(
            product,
            items=[
                {"product_id": product.id, "quantity": 1},
                {"product_id": 9999, "quantity": 1},
            ],
        ),
    )

    assert response.status_code == 404
    assert db.query(Order).count() == 0


def test_cart_pricing_endpoint_matches_the_order(
    client: TestClient, db: Session, delivery_area: DeliveryArea
) -> None:
    product = make_product(db, price="100.00", stock=10)
    _coupon(db, code="TEN")
    priced = client.post(
        "/api/v1/cart/price",
        json={
            "items": [{"product_id": product.id, "quantity": 2}],
            "coupon_code": "TEN",
            "delivery_area_id": delivery_area.id,
        },
    )
    assert priced.status_code == 200
    assert priced.json()["total"] == 200.0
    assert priced.json()["delivery_area_name"] == delivery_area.name


def test_order_lookup_requires_the_public_token(client: TestClient, db: Session) -> None:
    product = make_product(db, stock=5)
    created = client.post("/api/v1/orders", json=_order_payload(product)).json()

    ok = client.get(f"/api/v1/orders/{created['order_number']}", headers={"X-Order-Token": created["public_token"]})
    assert ok.status_code == 200
    assert ok.json()["order_number"] == created["order_number"]
    assert "admin_notes" not in ok.json()
    assert ok.headers["Cache-Control"] == "no-store"

    wrong = client.get(
        f"/api/v1/orders/{created['order_number']}", headers={"X-Order-Token": "wrong-token-value"}
    )
    assert wrong.status_code == 404

    missing = client.get(f"/api/v1/orders/{created['order_number']}")
    assert missing.status_code == 422
    assert "token=" not in str(ok.request.url)


def test_order_creation_is_rate_limited(client: TestClient, db: Session, monkeypatch) -> None:
    from app.core.config import settings
    from app.core.rate_limit import order_create_rate_limit

    monkeypatch.setattr(settings, "ORDER_CREATE_RATE_LIMIT", 1)
    order_create_rate_limit._hits.clear()
    product = make_product(db, stock=5)
    assert client.post("/api/v1/orders", json=_order_payload(product)).status_code == 201
    limited = client.post("/api/v1/orders", json=_order_payload(product))
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    order_create_rate_limit._hits.clear()


def test_unknown_status_is_rejected_by_the_service(db: Session) -> None:
    product = make_product(db, stock=5)
    order = orders_service.create_order(
        db,
        orders_service.OrderDraft(
            client_reference="service-ref-0001",
            customer_name="اسم",
            customer_phone="0591234567",
            address="عنوان كامل",
            items=[(product.id, None, 1)],
        ),
    )
    db.commit()
    with pytest.raises(DomainError):
        orders_service.change_status(db, order, "not-a-status")
    assert order.status == OrderStatus.NEW.value


def test_public_checkout_returns_a_canonical_new_order_snapshot_and_is_idempotent(
    client: TestClient, db: Session, delivery_area: DeliveryArea
) -> None:
    product = make_product(
        db,
        name="Server name",
        sku="SERVER-SKU",
        price="25.00",
        stock=10,
    )
    payload = _order_payload(
        product,
        client_reference="checkout-ref-0001",
        delivery_area_id=delivery_area.id,
        customer_notes="Leave at reception",
    )

    created = client.post("/api/v1/orders", json=payload)
    repeated = client.post("/api/v1/orders", json=payload)

    assert created.status_code == 201, created.text
    assert repeated.status_code == 201, repeated.text
    body = created.json()
    assert repeated.json()["id"] == body["id"]
    assert repeated.json()["order_number"] == body["order_number"]
    assert body["status"] == "new"
    assert body["source"] == "website"
    assert body["customer_phone"] == "0591234567"
    assert body["address"] == payload["address"]
    assert body["customer_notes"] == "Leave at reception"
    assert body["items"] == [
        {
            "id": body["items"][0]["id"],
            "product_id": product.id,
            "variant_id": None,
            "product_name": "Server name",
            "sku": "SERVER-SKU",
                "variant_description": None,
                "selected_option_value_ids": [],
            "unit_price": 25.0,
            "quantity": 2,
            "line_total": 50.0,
        }
    ]
    assert body["subtotal"] == 50.0
    assert body["discount"] == 0.0
    assert body["delivery_fee"] == 20.0
    assert body["total"] == 70.0
    assert db.query(Order).count() == 1


def test_public_checkout_recovers_from_a_concurrent_client_reference_conflict(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = make_product(db, stock=10)
    payload = _order_payload(product, client_reference="checkout-race-0001")
    created = client.post("/api/v1/orders", json=payload).json()

    def concurrent_conflict(*_args, **_kwargs):
        raise IntegrityError("INSERT INTO orders", {}, Exception("unique client reference"))

    monkeypatch.setattr(public_checkout.orders_service, "create_order", concurrent_conflict)
    recovered = public_checkout.create_order(OrderCreate.model_validate(payload), db, Response())

    assert recovered.id == created["id"]
    assert recovered.order_number == created["order_number"]
    assert db.query(Order).count() == 1
