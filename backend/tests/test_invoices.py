"""Invoicing: issuance, idempotency, immutability, numbering, cancellation, tax, access."""

from __future__ import annotations

from decimal import Decimal
from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import InvoiceStatus, OrderStatus
from app.models import DeliveryArea, Invoice, Order, Product
from app.services import invoices as invoices_service
from app.services import orders as orders_service
from app.services import store_settings as settings_service
from tests.conftest import auth, make_product

_client_reference_sequence = count(1)


def _place_order(
    client: TestClient,
    product: Product,
    *,
    quantity: int = 2,
    **overrides,
) -> dict:
    payload = {
        "client_reference": f"invoice-test-{next(_client_reference_sequence)}",
        "customer_name": "سارة أحمد",
        "customer_phone": "0591234567",
        "address": "رام الله، شارع الإرسال، بناية ٥",
        "items": [{"product_id": product.id, "quantity": quantity}],
    }
    payload.update(overrides)
    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _order_row(db: Session, order_number: str) -> Order:
    db.expire_all()
    return orders_service.get_by_number(db, order_number)


def _set_status(client: TestClient, token: str, order_id: int, status: str, note=None):
    return client.post(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": status, "note": note},
        headers=auth(token),
    )


def _complete_order(client: TestClient, token: str, order_id: int):
    return client.post(
        f"/api/v1/admin/orders/{order_id}/complete",
        json={"payment_method": "cash_on_delivery"},
        headers=auth(token),
    )


@pytest.fixture()
def product(db: Session, category) -> Product:
    return make_product(db, price="100.00", stock=50, category_id=category.id)


# ── issuance ─────────────────────────────────────────────────────────────────
def test_a_pending_order_has_no_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product)
    order = _order_row(db, created["order_number"])

    assert order.status == OrderStatus.NEW.value
    assert invoices_service.get_for_order(db, order.id) is None

    detail = client.get(f"/api/v1/admin/orders/{order.id}", headers=auth(admin_token))
    assert detail.json()["invoice"] is None

    missing = client.get(
        f"/api/v1/admin/orders/{order.id}/invoice", headers=auth(admin_token)
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "invoice_not_found"


def test_completing_an_order_issues_exactly_one_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product)
    order = _order_row(db, created["order_number"])

    response = _complete_order(client, admin_token, order.id)
    assert response.status_code == 200

    summary = response.json()["invoice"]
    assert summary is not None
    assert summary["status"] == InvoiceStatus.ISSUED.value
    assert summary["invoice_number"].startswith("INV-")

    db.expire_all()
    assert db.query(Invoice).filter(Invoice.order_id == order.id).count() == 1


def test_repeating_completion_creates_no_duplicate(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product)
    order = _order_row(db, created["order_number"])

    first = _complete_order(client, admin_token, order.id)
    number = first.json()["invoice"]["invoice_number"]

    # Repeating explicit completion is idempotent.
    again = _complete_order(client, admin_token, order.id)
    assert again.json()["invoice"]["invoice_number"] == number

    db.expire_all()
    assert db.query(Invoice).filter(Invoice.order_id == order.id).count() == 1


def test_a_replaced_invoice_and_its_active_replacement_can_share_an_order(
    db: Session, product: Product
) -> None:
    """Archived invoices remain when a corrected invoice replaces them."""

    order = orders_service.create_order(
        db,
        orders_service.OrderDraft(
            customer_name="سارة أحمد",
            customer_phone="0591234567",
            address="رام الله، شارع الإرسال",
            items=[(product.id, None, 1)],
        ),
    )
    db.commit()

    first = invoices_service.issue_for_order(db, order)
    db.commit()

    first.status = InvoiceStatus.REPLACED.value
    first.active_invoice_marker = None
    replacement = Invoice(
        invoice_number="INV-999999",
        order_id=order.id,
        status=InvoiceStatus.ACTIVE.value,
        active_invoice_marker=InvoiceStatus.ACTIVE.value,
            order_number=order.order_number,
            source=order.source,
        payment_method=order.payment_method,
        store_name="Store",
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        delivery_address=order.address,
        currency_code="ILS",
        currency_symbol="₪",
        subtotal=order.subtotal,
        discount=order.discount,
        delivery_fee=order.delivery_fee,
        tax_amount=Decimal("0.00"),
        grand_total=order.total,
        replacement_invoice=first,
    )
    db.add(replacement)
    db.commit()

    assert replacement.replacement_invoice_id == first.id
    assert replacement.invoice_number == "INV-999999"


# ── numbering ────────────────────────────────────────────────────────────────
def test_invoice_numbers_are_sequential_and_unique(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    numbers = []
    for _ in range(3):
        created = _place_order(client, product, quantity=1)
        order = _order_row(db, created["order_number"])
        response = _complete_order(client, admin_token, order.id)
        numbers.append(response.json()["invoice"]["invoice_number"])

    assert numbers == ["INV-000001", "INV-000002", "INV-000003"]
    assert len(set(numbers)) == 3


def test_a_completed_invoice_number_is_never_reused(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    first = _place_order(client, product, quantity=1)
    first_order = _order_row(db, first["order_number"])
    completed = _complete_order(client, admin_token, first_order.id)
    burned_number = completed.json()["invoice"]["invoice_number"]

    second = _place_order(client, product, quantity=1)
    second_order = _order_row(db, second["order_number"])
    reissued = _complete_order(client, admin_token, second_order.id)

    assert reissued.json()["invoice"]["invoice_number"] != burned_number
    assert reissued.json()["invoice"]["invoice_number"] == "INV-000002"


def test_the_number_prefix_is_configurable(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    client.patch(
        "/api/v1/admin/settings",
        json={"invoice_prefix": "VS"},
        headers=auth(admin_token),
    )
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    response = _complete_order(client, admin_token, order.id)

    assert response.json()["invoice"]["invoice_number"] == "VS-000001"


# ── the snapshot ─────────────────────────────────────────────────────────────
def test_the_invoice_matches_the_order_it_was_issued_for(
    client: TestClient,
    db: Session,
    product: Product,
    admin_token: str,
    delivery_area: DeliveryArea,
) -> None:
    settings_row = settings_service.get_or_create_settings(db)
    settings_row.store_name = "Vista Store"
    settings_row.store_name_ar = "متجر فيستا"
    settings_row.phone = "0000000000"
    db.commit()

    created = _place_order(
        client,
        product,
        quantity=2,
        delivery_area_id=delivery_area.id,
        customer_email="sara@example.com",
        customer_notes="اتصلوا قبل التوصيل",
    )
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    invoice = client.get(
        f"/api/v1/admin/orders/{order.id}/invoice", headers=auth(admin_token)
    ).json()

    assert invoice["order_number"] == order.order_number
    assert invoice["store_name"] == "متجر فيستا"
    assert invoice["store_phone"] == "0000000000"
    assert invoice["customer_name"] == "سارة أحمد"
    assert invoice["customer_phone"] == "0591234567"
    assert invoice["customer_email"] == "sara@example.com"
    assert invoice["delivery_address"] == order.address
    assert invoice["delivery_area_name"] == delivery_area.name
    assert invoice["customer_notes"] == "اتصلوا قبل التوصيل"
    assert invoice["payment_method"] == "cash_on_delivery"
    assert invoice["currency_code"] == "ILS"
    assert invoice["subtotal"] == float(order.subtotal)
    assert invoice["discount"] == float(order.discount)
    assert invoice["delivery_fee"] == float(order.delivery_fee)
    assert invoice["grand_total"] == float(order.total)
    assert invoice["status"] == InvoiceStatus.ISSUED.value

    assert len(invoice["items"]) == 1
    line = invoice["items"][0]
    assert line["product_name"] == product.name
    assert line["quantity"] == 2
    assert line["unit_price"] == 100.0
    assert line["line_total"] == 200.0


def test_editing_the_product_afterwards_does_not_change_the_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=2)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    number = invoices_service.get_for_order(db, order.id).invoice_number

    client.patch(
        f"/api/v1/admin/products/{product.id}",
        json={"price": 999, "name": "اسم جديد تماماً"},
        headers=auth(admin_token),
    )

    invoice = client.get(
        f"/api/v1/admin/invoices/{number}", headers=auth(admin_token)
    ).json()
    assert invoice["items"][0]["unit_price"] == 100.0
    assert invoice["items"][0]["line_total"] == 200.0
    assert invoice["items"][0]["product_name"] != "اسم جديد تماماً"
    assert invoice["grand_total"] == 200.0


def test_renaming_the_store_afterwards_does_not_change_the_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)
    number = invoices_service.get_for_order(db, order.id).invoice_number

    client.patch(
        "/api/v1/admin/settings",
        json={"store_name": "متجر آخر", "phone": "0599999999"},
        headers=auth(admin_token),
    )

    invoice = client.get(
        f"/api/v1/admin/invoices/{number}", headers=auth(admin_token)
    ).json()
    assert invoice["store_name"] != "متجر آخر"


def test_an_issued_invoice_cannot_be_edited_or_deleted(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)
    number = invoices_service.get_for_order(db, order.id).invoice_number

    for method in ("patch", "put"):
        response = getattr(client, method)(
            f"/api/v1/admin/invoices/{number}",
            json={"grand_total": 1},
            headers=auth(admin_token),
        )
        assert response.status_code == 405

    assert (
        client.delete(f"/api/v1/admin/invoices/{number}", headers=auth(admin_token)).status_code
        == 405
    )


# ── cancellation ─────────────────────────────────────────────────────────────
def test_cancelling_a_completed_order_is_rejected_and_keeps_its_active_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=2)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)
    number = invoices_service.get_for_order(db, order.id).invoice_number

    rejected = _set_status(
        client, admin_token, order.id, OrderStatus.CANCELLED.value, note="طلب العميل الإلغاء"
    )

    invoice = client.get(
        f"/api/v1/admin/invoices/{number}", headers=auth(admin_token)
    ).json()
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "order_locked"
    assert invoice["status"] == InvoiceStatus.ACTIVE.value
    assert invoice["invoice_number"] == number
    assert invoice["cancelled_at"] is None
    assert invoice["cancellation_reason"] is None
    assert invoice["cancelled_by_admin_id"] is None
    # The completed snapshot remains untouched.
    assert invoice["grand_total"] == 200.0
    assert len(invoice["items"]) == 1


def test_cancelling_from_the_invoice_screen_rejects_a_completed_order(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=2)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)
    number = invoices_service.get_for_order(db, order.id).invoice_number

    response = client.post(
        f"/api/v1/admin/invoices/{number}/cancel",
        json={"reason": "نفدت الكمية"},
        headers=auth(admin_token),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "order_locked"

    order_detail = client.get(
        f"/api/v1/admin/orders/{order.id}", headers=auth(admin_token)
    ).json()
    assert order_detail["status"] == OrderStatus.COMPLETED.value

    # Rejection does not restore reserved stock.
    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 48


def test_repeated_invoice_cancellation_cannot_modify_a_completed_order(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=2)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)
    number = invoices_service.get_for_order(db, order.id).invoice_number

    first = client.post(
        f"/api/v1/admin/invoices/{number}/cancel", json={}, headers=auth(admin_token)
    )
    assert first.status_code == 400
    assert first.json()["error"]["code"] == "order_locked"

    second = client.post(
        f"/api/v1/admin/invoices/{number}/cancel", json={}, headers=auth(admin_token)
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "order_locked"

    # Repeated rejection leaves stock unchanged.
    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 48


def test_a_cancelled_order_never_gets_a_second_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    _set_status(client, admin_token, order.id, OrderStatus.CANCELLED.value)

    # A cancelled order refuses completion, so it can never receive an invoice.
    blocked = _complete_order(client, admin_token, order.id)
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "order_cancelled"

    db.expire_all()
    assert db.query(Invoice).filter(Invoice.order_id == order.id).count() == 0


def test_cancelling_an_uninvoiced_order_still_works(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=2)
    order = _order_row(db, created["order_number"])

    response = _set_status(client, admin_token, order.id, OrderStatus.CANCELLED.value)
    assert response.status_code == 200
    assert response.json()["invoice"] is None

    db.expire_all()
    assert db.get(Product, product.id).stock_quantity == 50


# ── tax ──────────────────────────────────────────────────────────────────────
def test_tax_is_disabled_by_default_and_totals_match_the_order(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    settings_row = settings_service.get_or_create_settings(db)
    db.commit()
    assert settings_row.tax_enabled is False
    assert settings_row.tax_rate == Decimal("0.000")

    created = _place_order(client, product, quantity=3)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    invoice = invoices_service.get_for_order(db, order.id)
    assert invoice.tax_enabled is False
    assert invoice.tax_amount == Decimal("0.00")
    assert invoice.grand_total == order.total


def test_enabling_exclusive_tax_adds_it_on_top(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    client.patch(
        "/api/v1/admin/settings",
        json={"tax_enabled": True, "tax_rate": 16, "prices_include_tax": False},
        headers=auth(admin_token),
    )
    created = _place_order(client, product, quantity=1)  # total 100.00
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    invoice = invoices_service.get_for_order(db, order.id)
    assert invoice.tax_amount == Decimal("16.00")
    assert invoice.grand_total == Decimal("116.00")


def test_inclusive_tax_is_reported_without_inflating_the_total(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    client.patch(
        "/api/v1/admin/settings",
        json={"tax_enabled": True, "tax_rate": 16, "prices_include_tax": True},
        headers=auth(admin_token),
    )
    created = _place_order(client, product, quantity=1)  # total 100.00
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    invoice = invoices_service.get_for_order(db, order.id)
    assert invoice.grand_total == order.total == Decimal("100.00")
    assert invoice.tax_amount == Decimal("13.79")


def test_legal_and_tax_identity_is_blank_unless_the_owner_sets_it(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    invoice = invoices_service.get_for_order(db, order.id)
    assert invoice.legal_business_name is None
    assert invoice.registration_number is None
    assert invoice.tax_number is None


# ── admin list, search and filters ───────────────────────────────────────────
def _two_invoices(client: TestClient, db: Session, product: Product, token: str) -> list[str]:
    numbers = []
    for name in ("سارة أحمد", "محمود خالد"):
        created = _place_order(client, product, quantity=1, customer_name=name)
        order = _order_row(db, created["order_number"])
        response = _complete_order(client, token, order.id)
        numbers.append(response.json()["invoice"]["invoice_number"])
    return numbers


def test_the_invoice_list_returns_what_the_screen_needs(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    _two_invoices(client, db, product, admin_token)

    body = client.get("/api/v1/admin/invoices", headers=auth(admin_token)).json()
    assert body["total"] == 2
    row = body["items"][0]
    for field in (
        "invoice_number",
        "order_number",
        "customer_name",
        "issued_at",
        "grand_total",
        "payment_method",
        "status",
    ):
        assert field in row


def test_invoices_can_be_searched_by_number_order_and_customer(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    numbers = _two_invoices(client, db, product, admin_token)

    by_number = client.get(
        "/api/v1/admin/invoices", params={"q": numbers[1]}, headers=auth(admin_token)
    ).json()
    assert by_number["total"] == 1
    assert by_number["items"][0]["invoice_number"] == numbers[1]

    order_number = by_number["items"][0]["order_number"]
    by_order = client.get(
        "/api/v1/admin/invoices", params={"q": order_number}, headers=auth(admin_token)
    ).json()
    assert by_order["total"] == 1

    by_customer = client.get(
        "/api/v1/admin/invoices", params={"q": "محمود"}, headers=auth(admin_token)
    ).json()
    assert by_customer["total"] == 1
    assert by_customer["items"][0]["customer_name"] == "محمود خالد"


def test_invoices_can_be_filtered_by_status_and_date(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    numbers = _two_invoices(client, db, product, admin_token)
    active = client.get(
        "/api/v1/admin/invoices", params={"status": "active"}, headers=auth(admin_token)
    ).json()
    assert {row["invoice_number"] for row in active["items"]} == set(numbers)

    today = client.get(
        "/api/v1/admin/invoices",
        params={"issued_from": "2000-01-01", "issued_to": "2099-12-31"},
        headers=auth(admin_token),
    ).json()
    assert today["total"] == 2

    long_ago = client.get(
        "/api/v1/admin/invoices",
        params={"issued_to": "2000-01-01"},
        headers=auth(admin_token),
    ).json()
    assert long_ago["total"] == 0


def test_invoice_payment_updates_are_audited_and_filterable(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1, client_reference="payment-list-1")
    order = _order_row(db, created["order_number"])
    completed = client.post(
        f"/api/v1/admin/orders/{order.id}/complete",
        json={"payment_method": "cash_on_delivery"},
        headers=auth(admin_token),
    )
    number = completed.json()["invoice"]["invoice_number"]

    response = client.patch(
        f"/api/v1/admin/invoices/{number}/payment",
        json={"paid_amount": 40, "payment_method": "card", "payment_details": "receipt 7"},
        headers=auth(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["paid_amount"] == 40.0
    assert body["remaining_amount"] == 60.0
    assert body["payment_status"] == "partially_paid"
    assert body["payment_method"] == "card"
    payment_activity = body["activities"][-1]
    assert payment_activity["event_type"] == "payment_updated"
    assert payment_activity["before_data"]["payment_details"] is None
    assert payment_activity["after_data"]["payment_details"] == "receipt 7"

    filtered = client.get(
        "/api/v1/admin/invoices",
        params={"payment_status": "partially_paid", "source": "website", "employee_id": body["issued_by_admin_id"]},
        headers=auth(admin_token),
    )
    assert [row["invoice_number"] for row in filtered.json()["items"]] == [number]


def test_payment_corrections_and_refunds_are_super_admin_only(
    client: TestClient, db: Session, product: Product, admin_token: str, super_token: str
) -> None:
    created = _place_order(client, product, quantity=1, client_reference="payment-correction-1")
    order = _order_row(db, created["order_number"])
    completed = client.post(
        f"/api/v1/admin/orders/{order.id}/complete",
        json={"payment_method": "cash_on_delivery"},
        headers=auth(admin_token),
    )
    number = completed.json()["invoice"]["invoice_number"]
    assert client.patch(
        f"/api/v1/admin/invoices/{number}/payment", json={"paid_amount": 100}, headers=auth(admin_token)
    ).status_code == 200

    lowered = client.patch(
        f"/api/v1/admin/invoices/{number}/payment", json={"paid_amount": 90}, headers=auth(admin_token)
    )
    assert lowered.status_code == 403
    assert client.get(f"/api/v1/admin/invoices/{number}", headers=auth(admin_token)).json()["paid_amount"] == 100.0

    forbidden = client.patch(
        f"/api/v1/admin/invoices/{number}/payment", json={"refunded_amount": 10}, headers=auth(admin_token)
    )
    assert forbidden.status_code == 403

    missing_reason = client.patch(
        f"/api/v1/admin/invoices/{number}/payment", json={"refunded_amount": 10}, headers=auth(super_token)
    )
    assert missing_reason.status_code == 400

    refunded = client.patch(
        f"/api/v1/admin/invoices/{number}/payment",
        json={"refunded_amount": 10, "reason": "Returned one item"},
        headers=auth(super_token),
    )
    assert refunded.status_code == 200
    assert refunded.json()["payment_status"] == "partially_refunded"


def test_an_unknown_invoice_number_is_a_clean_404(
    client: TestClient, admin_token: str
) -> None:
    response = client.get("/api/v1/admin/invoices/INV-000999", headers=auth(admin_token))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invoice_not_found"


# ── authorization and privacy ────────────────────────────────────────────────
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/admin/invoices"),
        ("get", "/api/v1/admin/invoices/INV-000001"),
        ("get", "/api/v1/admin/orders/1/invoice"),
        ("post", "/api/v1/admin/invoices/INV-000001/cancel"),
    ],
)
def test_every_invoice_endpoint_requires_authentication(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_an_expired_or_bogus_token_is_refused(client: TestClient) -> None:
    response = client.get("/api/v1/admin/invoices", headers=auth("not-a-real-token"))
    assert response.status_code == 401


def test_a_normal_admin_may_use_the_invoice_screens(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    """Invoices are day-to-day work, not a super-admin-only area."""
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    assert client.get("/api/v1/admin/invoices", headers=auth(admin_token)).status_code == 200


def test_the_public_order_view_leaks_nothing_about_the_invoice(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1)
    order = _order_row(db, created["order_number"])
    _complete_order(client, admin_token, order.id)

    public = client.get(
        f"/api/v1/orders/{order.order_number}",
        headers={"X-Order-Token": created["public_token"]},
    )
    assert public.status_code == 200
    body = public.json()
    assert "invoice" not in body
    serialized = public.text
    assert "invoice_number" not in serialized
    assert "INV-" not in serialized
    # And no route exposes an invoice without a token.
    assert client.get("/api/v1/invoices").status_code == 404


def test_the_public_store_settings_never_expose_legal_or_tax_identity(
    client: TestClient, db: Session, admin_token: str
) -> None:
    client.patch(
        "/api/v1/admin/settings",
        json={
            "legal_business_name": "شركة تجريبية",
            "tax_number": "123456789",
            "registration_number": "RC-1",
            "tax_enabled": True,
            "tax_rate": 16,
        },
        headers=auth(admin_token),
    )
    body = client.get("/api/v1/store/settings").json()

    for leaked in (
        "legal_business_name",
        "tax_number",
        "registration_number",
        "tax_enabled",
        "tax_rate",
        "invoice_prefix",
    ):
        assert leaked not in body


# ── payment methods ──────────────────────────────────────────────────────────
def test_cash_on_delivery_is_the_default_and_completes_checkout(
    client: TestClient, db: Session, product: Product
) -> None:
    created = _place_order(client, product, quantity=1)
    assert created["payment_method"] == "cash_on_delivery"

    order = _order_row(db, created["order_number"])
    assert order.payment_method == "cash_on_delivery"
    assert order.status == OrderStatus.NEW.value


def test_unsupported_manual_payment_is_rejected(client: TestClient, product: Product) -> None:
    response = client.post("/api/v1/orders", json={"client_reference": "manual-payment-rejected", "customer_name": "Sara Ahmad", "customer_phone": "0591234567", "address": "Ramallah, Main Street 5", "payment_method": "manual", "items": [{"product_id": product.id, "quantity": 1}]})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "method",
    ["card", "credit_card", "stripe", "paypal", "online", "visa", ""],
)
def test_online_and_card_payment_methods_are_rejected(
    client: TestClient, product: Product, method: str
) -> None:
    response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "سارة أحمد",
            "customer_phone": "0591234567",
            "address": "رام الله، شارع الإرسال، بناية ٥",
            "payment_method": method,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_no_order_is_created_when_the_payment_method_is_rejected(
    client: TestClient, db: Session, product: Product
) -> None:
    client.post(
        "/api/v1/orders",
        json={
            "customer_name": "سارة أحمد",
            "customer_phone": "0591234567",
            "address": "رام الله، شارع الإرسال، بناية ٥",
            "payment_method": "credit_card",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    db.expire_all()
    assert db.query(Order).count() == 0
    assert db.get(Product, product.id).stock_quantity == 50


def test_the_admin_order_view_shows_the_payment_method(
    client: TestClient, db: Session, product: Product, admin_token: str
) -> None:
    created = _place_order(client, product, quantity=1, payment_method="card")
    order = _order_row(db, created["order_number"])

    detail = client.get(f"/api/v1/admin/orders/{order.id}", headers=auth(admin_token)).json()
    assert detail["payment_method"] == "card"

    listing = client.get("/api/v1/admin/orders", headers=auth(admin_token)).json()
    assert listing["items"][0]["payment_method"] == "card"


def test_manual_payment_instructions_are_blank_until_the_owner_supplies_them(
    client: TestClient, admin_token: str
) -> None:
    assert client.get("/api/v1/store/settings").json()["manual_payment_instructions"] is None

    client.patch(
        "/api/v1/admin/settings",
        json={"manual_payment_instructions": "بنك فلسطين — حساب رقم ..."},
        headers=auth(admin_token),
    )
    body = client.get("/api/v1/store/settings").json()
    assert body["manual_payment_instructions"] == "بنك فلسطين — حساب رقم ..."
