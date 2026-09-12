from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Invoice, Order, OrderItem, Product, ProductOption, ProductOptionValue
from tests.conftest import auth, make_product


def _create_order(client: TestClient, product: Product, **changes: object) -> dict:
    payload = {
        "client_reference": f"admin-edit-{product.id}-{changes.get('suffix', 'one')}",
        "customer_name": "Search Customer",
        "customer_phone": "0591234567",
        "address": "Ramallah, Main Street 10",
        "items": [{"product_id": product.id, "quantity": 1}],
    }
    payload.update({key: value for key, value in changes.items() if key != "suffix"})
    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _edit_payload(first: Product, second: Product | None = None, **changes: object) -> dict:
    payload = {
        "customer_name": "Edited Customer",
        "customer_phone": "0597654321",
        "customer_email": "edited@example.com",
        "address": "Ramallah, Edited Street 20",
        "payment_method": "cash_on_delivery",
        "customer_notes": "Customer note",
        "admin_notes": "Internal note",
        "discount": "5.00",
        "delivery_fee": "7.00",
        "status": "reviewing",
        "reason": "Customer agreed to the correction",
        "items": [
            {
                "product_id": first.id,
                "quantity": 2,
                "unit_price": "12.50",
            }
        ],
    }
    if second is not None:
        payload["items"].append({"product_id": second.id, "quantity": 3})
    payload.update(changes)
    return payload


def test_admin_order_list_filters_search_source_payment_date_and_paginates(
    client: TestClient, db: Session, admin_token: str
) -> None:
    first = make_product(db, slug="admin-list-first", name="First", price="10.00")
    second = make_product(db, slug="admin-list-second", name="Second", price="20.00")
    first_order = _create_order(client, first, suffix="first", customer_name="Mona Search")
    _create_order(client, second, suffix="second", customer_name="Other Customer")

    response = client.get(
        "/api/v1/admin/orders",
        headers=auth(admin_token),
        params={
            "q": "Mona",
            "source": "website",
            "payment_status": "unpaid",
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "page": 1,
            "page_size": 1,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["items"][0]["id"] == first_order["id"]
    assert body["items"][0]["source"] == "website"
    assert body["items"][0]["payment_status"] == "unpaid"


def test_admin_order_detail_exposes_original_current_invoices_and_activity(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-detail", name="Original product", price="10.00")
    order = _create_order(client, product)

    edited = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product),
    )
    assert edited.status_code == 200, edited.text

    body = client.get(f"/api/v1/admin/orders/{order['id']}", headers=auth(admin_token)).json()
    item = body["items"][0]
    assert item["original_unit_price"] == 10.0
    assert item["unit_price"] == 12.5
    assert body["source"] == "website"
    assert body["subtotal"] == 25.0
    assert body["total"] == 27.0
    assert body["final_review"]["total"] == 27.0
    assert body["final_review"]["items"][0]["unit_price"] == 12.5
    assert body["final_review"]["payment_method"] == "cash_on_delivery"
    assert body["active_invoice"] is None
    assert body["invoices"] == []
    assert [event["event_type"] for event in body["activities"]] == [
        "order_created",
        "order_item_quantity_changed",
        "order_item_price_changed",
        "order_discount_changed",
        "order_delivery_fee_changed",
        "order_customer_updated",
        "order_notes_updated",
        "order_status_changed",
    ]


def test_both_roles_edit_incomplete_website_order_without_changing_catalog_price(
    client: TestClient, db: Session, admin_token: str, super_token: str
) -> None:
    first = make_product(db, slug="admin-edit-first", name="First", price="10.00", stock=20)
    second = make_product(db, slug="admin-edit-second", name="Second", price="4.00", stock=20)
    order = _create_order(client, first)

    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(first, second),
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 39.0
    db.expire_all()
    assert db.get(Product, first.id).price == Decimal("10.00")
    assert db.get(Product, first.id).stock_quantity == 18
    assert db.get(Product, second.id).stock_quantity == 17

    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_edit_payload(second, reason="Manager correction"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["product_id"] == second.id


def test_edit_requires_reason_for_material_changes_and_rejects_locked_or_nonwebsite_orders(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-edit-rules", name="Rules", price="10.00")
    order = _create_order(client, product)

    no_reason = _edit_payload(product, reason=None)
    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}", headers=auth(admin_token), json=no_reason
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "edit_reason_required"

    db_order = db.get(Order, order["id"])
    db_order.is_locked = True
    db.commit()
    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "order_locked"

    db_order.is_locked = False
    db_order.source = "phone"
    db.commit()
    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "order_source_not_editable"


def test_edit_rejects_completed_or_cancelled_status_and_manual_items(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-edit-invalid", name="Invalid", price="10.00")
    order = _create_order(client, product)

    complete = _edit_payload(product, status="completed")
    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}", headers=auth(admin_token), json=complete
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "completion_requires_confirmation"

    manual = _edit_payload(product)
    manual["items"] = [{"kind": "manual", "name": "Manual", "quantity": 1, "unit_price": "1"}]
    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}", headers=auth(admin_token), json=manual
    )
    assert response.status_code == 403

    db_order = db.get(Order, order["id"])
    db_order.status = "cancelled"
    db.commit()
    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "order_cancelled"


def test_status_endpoint_cannot_complete_or_move_a_completed_order(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-status-completed", name="Status", price="10.00")
    order = _create_order(client, product)

    complete = client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        headers=auth(admin_token),
        json={"status": "completed"},
    )
    assert complete.status_code == 400
    assert complete.json()["error"]["code"] == "completion_requires_confirmation"

    db_order = db.get(Order, order["id"])
    db_order.status = "completed"
    db_order.is_locked = True
    db.commit()
    moved = client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        headers=auth(admin_token),
        json={"status": "reviewing"},
    )
    assert moved.status_code == 400
    assert moved.json()["error"]["code"] == "order_locked"


def test_notes_change_requires_reason_and_records_material_activity(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-notes-reason", name="Notes", price="10.00")
    order = _create_order(client, product)

    missing_reason = client.patch(
        f"/api/v1/admin/orders/{order['id']}/notes",
        headers=auth(admin_token),
        json={"admin_notes": "Call before delivery"},
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["error"]["code"] == "edit_reason_required"

    saved = client.patch(
        f"/api/v1/admin/orders/{order['id']}/notes",
        headers=auth(admin_token),
        json={
            "admin_notes": "Call before delivery",
            "reason": "Customer requested a phone call",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["admin_notes"] == "Call before delivery"
    event = saved.json()["activities"][-1]
    assert event["event_type"] == "order_notes_updated"
    assert event["reason"] == "Customer requested a phone call"


def test_full_order_edit_allows_internal_notes_only_without_reason(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-notes-full-edit", name="Notes edit", price="10.00")
    order = _create_order(client, product)
    first = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product),
    )
    assert first.status_code == 200, first.text

    notes_only = _edit_payload(product, admin_notes="Changed without reason", reason=None)
    updated = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=notes_only,
    )

    assert updated.status_code == 200


def test_edit_rejects_legacy_current_statuses_outside_approved_workflow(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="admin-legacy-status", name="Legacy", price="10.00")
    order = _create_order(client, product)
    db_order = db.get(Order, order["id"])
    db_order.status = "pending"
    db.commit()

    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product, status="reviewing"),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "order_status_not_editable"


def test_both_roles_complete_an_order_once_with_an_immutable_final_invoice(
    client: TestClient, db: Session, admin_token: str, super_token: str, normal_admin, super_admin
) -> None:
    product = make_product(db, slug="completion-snapshot", name="Final price", price="10.00")
    first_order_id: int | None = None

    for suffix, token, actor in (
        ("admin", admin_token, normal_admin),
        ("super", super_token, super_admin),
    ):
        order = _create_order(client, product, suffix=suffix)
        first_order_id = first_order_id or order["id"]
        completed = client.post(
            f"/api/v1/admin/orders/{order['id']}/complete",
            headers=auth(token),
            json={
                "payment_method": "card",
                "paid_amount": "5.00",
                "payment_details": "Cash received",
                "invoice_notes": "Final internal note",
            },
        )

        assert completed.status_code == 200, completed.text
        body = completed.json()
        assert body["status"] == "completed"
        assert body["is_locked"] is True
        assert body["completed_at"] is not None
        assert body["completed_by_admin_id"] is not None
        assert body["active_invoice"] is not None

        invoice = client.get(
            f"/api/v1/admin/orders/{order['id']}/invoice", headers=auth(token)
        ).json()
        assert invoice["payment_method"] == "card"
        assert invoice["paid_amount"] == 5.0
        assert invoice["remaining_amount"] == 5.0
        assert invoice["payment_details"] == "Cash received"
        assert invoice["invoice_notes"] == "Final internal note"
        assert invoice["issued_by_admin_id"] == actor.id
        assert invoice["issued_by_admin_name"] == actor.full_name
        assert invoice["issued_by_admin_email"] == actor.email
        assert invoice["items"][0]["unit_price"] == 10.0

        retried = client.post(
            f"/api/v1/admin/orders/{order['id']}/complete",
            headers=auth(token),
            json={"payment_method": "card", "paid_amount": "5.00"},
        )
        assert retried.status_code == 200, retried.text
        db.expire_all()
        assert db.query(Invoice).filter(Invoice.order_id == order["id"]).count() == 1

    product.price = Decimal("777.00")
    db.commit()
    invoice = client.get(
        f"/api/v1/admin/orders/{first_order_id}/invoice", headers=auth(admin_token)
    ).json()
    assert invoice["items"][0]["unit_price"] == 10.0


def test_super_admin_reopens_completed_order_replaces_invoice_and_recompletion_links_history(
    client: TestClient,
    db: Session,
    admin_token: str,
    super_token: str,
    super_admin,
) -> None:
    """Removing the reopen transition must leave the completed financial snapshot locked."""
    product = make_product(db, slug="reopen-history", name="Reopen history", price="10.00")
    order = _create_order(client, product, suffix="reopen-history")
    completed = client.post(
        f"/api/v1/admin/orders/{order['id']}/complete",
        headers=auth(admin_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert completed.status_code == 200, completed.text
    old_invoice_id = completed.json()["active_invoice"]["id"]

    reopened = client.post(
        f"/api/v1/admin/orders/{order['id']}/reopen",
        headers=auth(super_token),
        json={"reason": "Correct the delivery address"},
    )

    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["is_locked"] is False
    assert reopened.json()["active_invoice"] is None
    assert reopened.json()["invoices"][0]["status"] == "replaced"

    blocked_edit = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_edit_payload(product),
    )
    assert blocked_edit.status_code == 403

    corrected = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_edit_payload(product, address="Ramallah, Corrected Street 30"),
    )
    assert corrected.status_code == 200, corrected.text
    recompleted = client.post(
        f"/api/v1/admin/orders/{order['id']}/complete",
        headers=auth(super_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert recompleted.status_code == 200, recompleted.text

    db.expire_all()
    invoices = db.query(Invoice).filter(Invoice.order_id == order["id"]).order_by(Invoice.id).all()
    assert len(invoices) == 2
    old, replacement = invoices
    assert old.id == old_invoice_id
    assert old.status == "replaced"
    assert old.active_invoice_marker is None
    assert replacement.status == "active"
    assert replacement.active_invoice_marker == "active"
    assert replacement.replacement_invoice_id == old.id
    assert replacement.invoice_number != old.invoice_number
    assert db.query(Invoice).filter(Invoice.order_id == order["id"], Invoice.status == "active").count() == 1

    activities = db.get(Order, order["id"]).activities
    reopened_activity = next(activity for activity in activities if activity.event_type == "order_reopened")
    assert reopened_activity.invoice_id == old.id
    assert reopened_activity.actor_admin_id == super_admin.id
    assert reopened_activity.reason == "Correct the delivery address"


def test_reopen_requires_super_admin_reason_and_completed_active_invoice(
    client: TestClient, db: Session, admin_token: str, super_token: str
) -> None:
    """Removing any reopen precondition would allow unauthorized or non-final corrections."""
    product = make_product(db, slug="reopen-guards", name="Reopen guards", price="10.00")
    order = _create_order(client, product, suffix="reopen-guards")
    path = f"/api/v1/admin/orders/{order['id']}/reopen"

    assert client.post(path, headers=auth(admin_token), json={"reason": "Correction"}).status_code == 403
    assert client.post(path, headers=auth(super_token), json={}).status_code == 422
    not_completed = client.post(path, headers=auth(super_token), json={"reason": "Correction"})
    assert not_completed.status_code == 400
    assert not_completed.json()["error"]["code"] == "order_not_completed"

    completed = client.post(
        f"/api/v1/admin/orders/{order['id']}/complete",
        headers=auth(super_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert completed.status_code == 200, completed.text
    invoice = db.get(Invoice, completed.json()["active_invoice"]["id"])
    invoice.status = "replaced"
    invoice.active_invoice_marker = None
    db.commit()

    missing_invoice = client.post(path, headers=auth(super_token), json={"reason": "Correction"})
    assert missing_invoice.status_code == 400
    assert missing_invoice.json()["error"]["code"] == "active_invoice_required"


def test_repeated_reopen_recompletion_links_each_invoice_to_its_predecessor(
    client: TestClient, db: Session, super_token: str
) -> None:
    """Choosing the original replaced invoice again breaks a correction history chain."""
    product = make_product(db, slug="reopen-chain", name="Reopen chain", price="10.00")
    order = _create_order(client, product, suffix="reopen-chain")
    complete_path = f"/api/v1/admin/orders/{order['id']}/complete"
    reopen_path = f"/api/v1/admin/orders/{order['id']}/reopen"

    first = client.post(
        complete_path,
        headers=auth(super_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["active_invoice"]["id"]
    first_reopen = client.post(
        reopen_path, headers=auth(super_token), json={"reason": "First correction"}
    )
    assert first_reopen.status_code == 200, first_reopen.text

    second = client.post(
        complete_path,
        headers=auth(super_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["active_invoice"]["id"]
    second_reopen = client.post(
        reopen_path, headers=auth(super_token), json={"reason": "Second correction"}
    )
    assert second_reopen.status_code == 200, second_reopen.text

    third = client.post(
        complete_path,
        headers=auth(super_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert third.status_code == 200, third.text

    db.expire_all()
    invoices = db.query(Invoice).filter(Invoice.order_id == order["id"]).order_by(Invoice.id).all()
    assert len(invoices) == 3
    assert invoices[0].id == first_id
    assert invoices[1].id == second_id
    assert invoices[0].status == "replaced"
    assert invoices[1].status == "replaced"
    assert invoices[2].status == "active"
    assert invoices[1].replacement_invoice_id == invoices[0].id
    assert invoices[2].replacement_invoice_id == invoices[1].id
    assert db.query(Invoice).filter(Invoice.order_id == order["id"], Invoice.status == "active").count() == 1


def test_completion_rejects_cancelled_and_empty_orders_without_an_invoice(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="completion-rejections", name="Reject", price="10.00")
    cancelled = _create_order(client, product, suffix="cancelled")
    client.post(
        f"/api/v1/admin/orders/{cancelled['id']}/status",
        headers=auth(admin_token),
        json={"status": "cancelled"},
    )
    blocked = client.post(
        f"/api/v1/admin/orders/{cancelled['id']}/complete",
        headers=auth(admin_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "order_cancelled"

    empty = _create_order(client, product, suffix="empty")
    db.query(OrderItem).filter(OrderItem.order_id == empty["id"]).delete()
    db.commit()
    blocked = client.post(
        f"/api/v1/admin/orders/{empty['id']}/complete",
        headers=auth(admin_token),
        json={"payment_method": "cash_on_delivery", "paid_amount": "0.00"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "empty_order"
    db.expire_all()
    assert db.get(Order, empty["id"]).status != "completed"
    assert db.query(Invoice).filter(Invoice.order_id == empty["id"]).count() == 0


def _manual_order_payload(product: Product, **changes: object) -> dict:
    payload = {
        "source": "whatsapp",
        "source_note": "WhatsApp conversation",
        "customer_name": "Manual Customer",
        "customer_phone": "0591234567",
        "address": "Ramallah, Manual Street 10",
        "payment_method": "card",
        "customer_notes": "Customer requested pickup",
        "admin_notes": "Entered by manager",
        "discount": "5.00",
        "delivery_fee": "7.00",
        "items": [
            {"kind": "catalog", "product_id": product.id, "quantity": 2, "unit_price": "12.50"},
            {
                "kind": "manual",
                "name": "Custom gift wrap",
                "description": "Blue ribbon",
                "quantity": 3,
                "unit_price": "1.25",
            },
        ],
    }
    payload.update(changes)
    return payload


def test_super_admin_saves_mixed_manual_order_without_invoice_or_manual_catalog_changes(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-mixed", name="Catalog line", price="10.00", stock=20)
    products_before = db.query(Product).count()

    response = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "whatsapp"
    assert body["status"] == "new"
    assert body["subtotal"] == 28.75
    assert body["total"] == 30.75
    assert body["active_invoice"] is None
    assert body["invoices"] == []
    catalog, manual = body["items"]
    assert catalog["product_id"] == product.id
    assert catalog["original_unit_price"] == 10.0
    assert catalog["unit_price"] == 12.5
    assert manual["item_kind"] == "manual"
    assert manual["product_id"] is None
    assert manual["product_name"] == "Custom gift wrap"
    assert manual["manual_description"] == "Blue ribbon"
    db.expire_all()
    assert db.get(Product, product.id).price == Decimal("10.00")
    assert db.get(Product, product.id).stock_quantity == 18
    assert db.query(Product).count() == products_before
    assert db.query(Invoice).filter(Invoice.order_id == body["id"]).count() == 0


def test_manual_order_resolves_and_snapshots_simple_product_options(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-simple-options", name="شمعة لافندر", price="70.00", stock=10)
    size = ProductOption(product_id=product.id, name="الحجم", affects_price=True, sort_order=0)
    large = ProductOptionValue(value="كبير", price_override=Decimal("90.00"), sort_order=0)
    size.values.append(large)
    db.add(size)
    db.commit()

    base_response = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product, items=[{
            "kind": "catalog", "product_id": product.id, "quantity": 1,
        }]),
    )
    assert base_response.status_code == 201, base_response.text
    base_item = base_response.json()["items"][0]
    assert base_item["selected_option_value_ids"] == []
    assert base_item["variant_description"] is None
    assert base_item["unit_price"] == 70

    response = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product, items=[{
            "kind": "catalog", "product_id": product.id,
            "selected_option_value_ids": [large.id], "quantity": 2,
        }]),
    )

    assert response.status_code == 201, response.text
    item = response.json()["items"][0]
    assert item["selected_option_value_ids"] == [large.id]
    assert item["variant_description"] == "الحجم: كبير"
    assert item["unit_price"] == 90
    assert item["line_total"] == 180


def _manual_edit_payload(order: dict, items: list[dict]) -> dict:
    return {
        "customer_name": order["customer_name"],
        "customer_phone": order["customer_phone"],
        "customer_email": order["customer_email"],
        "address": "Ramallah, Corrected Manual Street 20",
        "payment_method": order["payment_method"],
        "customer_notes": order["customer_notes"],
        "admin_notes": "Corrected by manager",
        "discount": str(order["discount"]),
        "delivery_fee": str(order["delivery_fee"]),
        "status": "reviewing",
        "reason": "Correct the saved manual order",
        "items": items,
    }


def test_super_admin_can_replace_incomplete_manual_order_items_with_manual_items(
    client: TestClient,
    db: Session,
    super_token: str,
) -> None:
    product = make_product(db, slug="manual-edit", name="Catalog line", price="10.00", stock=20)
    created = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product),
    )
    assert created.status_code == 201, created.text
    order = created.json()
    edited = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "manual", "name": "Updated gift wrap", "quantity": 2, "unit_price": "2.00"}],
        ),
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert [item["item_kind"] for item in body["items"]] == ["manual"]


def test_super_admin_can_edit_manual_item_fields(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-item-fields", name="Catalog line", price="10.00")
    created = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    assert created.status_code == 201, created.text
    order = created.json()
    manual_item = next(item for item in order["items"] if item["item_kind"] == "manual")

    edited = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "manual", "name": " Updated gift wrap ", "description": "Red ribbon", "quantity": 2, "unit_price": "2.00"}],
        ),
    )
    assert edited.status_code == 200, edited.text
    item = edited.json()["items"][0]
    assert item["product_name"] == "Updated gift wrap"
    assert item["manual_description"] == "Red ribbon"
    assert item["quantity"] == 2
    assert item["unit_price"] == 2.0


def test_manual_item_edit_records_actor_reason_and_field_before_after(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-item-activity", name="Catalog line", price="10.00")
    created = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    assert created.status_code == 201, created.text
    order = created.json()
    manual_item = next(item for item in order["items"] if item["item_kind"] == "manual")

    edited = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "manual", "order_item_id": manual_item["id"], "name": "Updated gift wrap", "description": "Red ribbon", "quantity": 2, "unit_price": "2.00"}],
        ),
    )
    assert edited.status_code == 200, edited.text
    event = next(event for event in edited.json()["activities"] if event["event_type"] == "order_manual_item_name_changed")
    assert event["actor_admin_id"] is not None
    assert event["reason"] == "Correct the saved manual order"
    assert event["before_data"]["product_name"] == "Custom gift wrap"
    assert event["after_data"]["product_name"] == "Updated gift wrap"


def test_admin_cannot_structurally_edit_order_containing_manual_item(
    client: TestClient, db: Session, admin_token: str, super_token: str
) -> None:
    product = make_product(db, slug="manual-edit-forbidden", name="Catalog line", price="10.00")
    created = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    assert created.status_code == 201, created.text
    order = created.json()

    forbidden = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(admin_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "manual", "name": "Updated gift wrap", "quantity": 2, "unit_price": "2.00"}],
        ),
    )
    assert forbidden.status_code == 403


def test_manual_order_edit_does_not_create_products_or_change_inventory(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-edit-isolation", name="Catalog line", price="10.00", stock=20)
    products_before = db.query(Product).count()
    created = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product, items=[{"kind": "manual", "name": "Gift wrap", "quantity": 1, "unit_price": "1.25"}]),
    )
    assert created.status_code == 201, created.text
    order = created.json()
    stock_before = db.get(Product, product.id).stock_quantity

    edited = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "manual", "name": "Gift wrap", "description": "Red ribbon", "quantity": 2, "unit_price": "2.00"}],
        ),
    )
    assert edited.status_code == 200, edited.text
    db.expire_all()
    assert db.query(Product).count() == products_before
    assert db.get(Product, product.id).stock_quantity == stock_before


def test_manual_edit_rejects_order_item_id_from_another_order(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-cross-order-id", name="Catalog line", price="10.00")
    first = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    second = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    assert first.status_code == second.status_code == 201
    first_order = first.json()
    foreign_item = next(item for item in second.json()["items"] if item["item_kind"] == "manual")

    response = client.patch(
        f"/api/v1/admin/orders/{first_order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            first_order,
            [{"kind": "manual", "order_item_id": foreign_item["id"], "name": "Gift wrap", "quantity": 1, "unit_price": "1.25"}],
        ),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "order_item_not_found"


def test_existing_manual_item_id_preserves_original_price_snapshot(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-original-price", name="Catalog line", price="10.00")
    created = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    assert created.status_code == 201, created.text
    order = created.json()
    manual_item = next(item for item in order["items"] if item["item_kind"] == "manual")

    edited = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "manual", "order_item_id": manual_item["id"], "name": "Updated gift wrap", "description": "Red ribbon", "quantity": 2, "unit_price": "2.00"}],
        ),
    )
    assert edited.status_code == 200, edited.text
    item = edited.json()["items"][0]
    assert item["id"] == manual_item["id"]
    assert item["product_id"] is None
    assert item["original_unit_price"] == 1.25
    assert item["unit_price"] == 2.0


def test_manual_item_id_cannot_be_submitted_as_a_catalog_item(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-kind-conversion", name="Catalog line", price="10.00")
    created = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=_manual_order_payload(product))
    assert created.status_code == 201, created.text
    order = created.json()
    manual_item = next(item for item in order["items"] if item["item_kind"] == "manual")

    response = client.patch(
        f"/api/v1/admin/orders/{order['id']}",
        headers=auth(super_token),
        json=_manual_edit_payload(
            order,
            [{"kind": "catalog", "order_item_id": manual_item["id"], "product_id": product.id, "quantity": 1}],
        ),
    )

    assert response.status_code == 422


def test_manual_order_requires_super_admin_and_rejects_empty_or_website_source(
    client: TestClient, db: Session, admin_token: str, super_token: str
) -> None:
    product = make_product(db, slug="manual-restrictions", name="Manual restrictions")

    forbidden = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(admin_token),
        json=_manual_order_payload(product),
    )
    assert forbidden.status_code == 403

    empty = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product, items=[]),
    )
    assert empty.status_code == 422

    website = client.post(
        "/api/v1/admin/orders/manual",
        headers=auth(super_token),
        json=_manual_order_payload(product, source="website"),
    )
    assert website.status_code == 422


def test_super_admin_can_complete_manual_order_with_one_active_invoice(
    client: TestClient, db: Session, super_token: str
) -> None:
    product = make_product(db, slug="manual-complete", name="Manual completion")
    payload = _manual_order_payload(
        product,
        completion={
                "payment_method": "card",
            "paid_amount": "5.00",
            "payment_details": "Cash received",
            "invoice_notes": "Manual order invoice",
        },
    )

    response = client.post("/api/v1/admin/orders/manual", headers=auth(super_token), json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["is_locked"] is True
    assert body["active_invoice"] is not None
    db.expire_all()
    assert db.query(Invoice).filter(Invoice.order_id == body["id"], Invoice.status == "active").count() == 1
