from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import PaymentStatus
from app.models import Order
from app.services import invoices as invoices_service
from app.services import orders as orders_service
from app.services.errors import DomainError
from app.services.invoices import validate_payment_update
from app.services.orders import calculate_order_totals, record_order_activity
from tests.conftest import make_product


LEGACY_STATUSES = ["confirmed", "delivered", "pending", "reviewing", "processing", "preparing", "out_for_delivery", "shipped"]


@pytest.mark.parametrize("status", LEGACY_STATUSES)
def test_status_mutation_schemas_reject_legacy_targets(status) -> None:
    from pydantic import ValidationError
    from app.schemas.orders import OrderAdminUpdate, OrderStatusUpdate

    with pytest.raises(ValidationError):
        OrderStatusUpdate(status=status)
    with pytest.raises(ValidationError):
        OrderAdminUpdate(
            customer_name="Customer", customer_phone="0590000000", address="Address",
            payment_method="cash_on_delivery", discount="0", delivery_fee="0",
            status=status, items=[{"kind": "manual", "name": "Item", "quantity": 1, "unit_price": "10"}],
        )


@pytest.mark.parametrize("status", LEGACY_STATUSES)
def test_change_status_rejects_legacy_targets(db, status) -> None:
    order = Order(status="new")
    with pytest.raises(DomainError) as error:
        orders_service.change_status(db, order, status)
    assert error.value.code == "invalid_status"
    assert order.status == "new"


def test_new_and_ready_orders_have_no_invoice(db, category, normal_admin) -> None:
    product = make_product(db, category_id=category.id, price="10.00")
    order = orders_service.create_order(db, orders_service.OrderDraft(
        customer_name="Customer", customer_phone="0590000000", address="Address",
        items=[(product.id, None, 1)],
    ))
    assert invoices_service.get_for_order(db, order.id) is None
    orders_service.change_status(db, order, "ready", admin=normal_admin)
    db.flush()
    assert order.status == "ready"
    assert invoices_service.get_for_order(db, order.id) is None


def test_reopen_persists_ready_status_and_canonical_snapshots(db, category, super_admin) -> None:
    product = make_product(db, category_id=category.id, price="10.00")
    order = orders_service.create_order(db, orders_service.OrderDraft(
        customer_name="Customer", customer_phone="0590000000", address="Address",
        items=[(product.id, None, 1)],
    ))
    orders_service.complete_order(
        db, order_id=order.id, admin=super_admin,
        payment_method="cash_on_delivery", payment_status="unpaid",
        payment_details=None, invoice_notes=None,
    )
    orders_service.reopen_completed_order(
        db, order_id=order.id, reason="Correct address", admin=super_admin,
    )
    db.commit()
    db.expire_all()

    saved = db.get(Order, order.id)
    assert saved.status == "ready"
    assert saved.is_locked is False
    assert saved.locked_at is None
    assert orders_service.can_structurally_edit_order(order=saved, actor=super_admin)
    reopened_history = next(row for row in saved.status_history if row.note == "Correct address")
    assert reopened_history.old_status == "completed"
    assert reopened_history.new_status == "ready"
    activity = next(row for row in saved.activities if row.event_type == "order_reopened")
    assert activity.before_data == {"status": "completed", "is_locked": True}
    assert activity.after_data["status"] == "ready"
    assert activity.after_data["is_locked"] is False


def test_completed_edit_eligibility_preserves_admin_role_and_source_boundaries() -> None:
    from types import SimpleNamespace

    order = SimpleNamespace(status="completed", source="website", items=[], is_locked=True)
    assert orders_service.can_structurally_edit_order(order=order, actor=SimpleNamespace(role="admin"))
    assert not orders_service.can_structurally_edit_order(order=order, actor=SimpleNamespace(role="viewer"))
    order.source = "whatsapp"
    assert not orders_service.can_structurally_edit_order(order=order, actor=SimpleNamespace(role="admin"))
    assert orders_service.can_structurally_edit_order(order=order, actor=SimpleNamespace(role="super_admin"))


@dataclass
class _Line:
    quantity: int
    unit_price: Decimal


def test_calculate_order_totals_quantizes_lines_and_never_returns_negative_total() -> None:
    totals = calculate_order_totals(
        [_Line(3, Decimal("1.005")), _Line(1, Decimal("2.004"))],
        discount_amount=Decimal("99.00"),
        delivery_fee=Decimal("0.005"),
    )

    assert totals.line_totals == (Decimal("3.03"), Decimal("2.00"))
    assert totals.subtotal == Decimal("5.03")
    assert totals.discount_amount == Decimal("99.00")
    assert totals.delivery_fee == Decimal("0.01")
    assert totals.total_amount == Decimal("0.00")


@pytest.mark.parametrize(
    ("items", "discount_amount", "delivery_fee"),
    [
        ([_Line(0, Decimal("1.00"))], Decimal("0.00"), Decimal("0.00")),
        ([_Line(1, Decimal("-1.00"))], Decimal("0.00"), Decimal("0.00")),
        ([_Line(1, Decimal("1.00"))], Decimal("-0.01"), Decimal("0.00")),
        ([_Line(1, Decimal("1.00"))], Decimal("0.00"), Decimal("-0.01")),
    ],
)
def test_calculate_order_totals_rejects_negative_money_and_nonpositive_quantities(
    items: list[_Line], discount_amount: Decimal, delivery_fee: Decimal
) -> None:
    with pytest.raises(DomainError):
        calculate_order_totals(items, discount_amount=discount_amount, delivery_fee=delivery_fee)


@pytest.mark.parametrize("total,status,paid,refunded,remaining", [
    ("10.00", "unpaid", "0.00", "0.00", "10.00"),
    ("10.00", "paid", "10.00", "0.00", "0.00"),
    ("10.00", "refunded", "10.00", "10.00", "0.00"),
    ("0.00", "unpaid", "0.00", "0.00", "0.00"),
    ("0.00", "paid", "0.00", "0.00", "0.00"),
    ("0.00", "refunded", "0.00", "0.00", "0.00"),
])
def test_payment_validation_derives_money_from_requested_state(total, status, paid, refunded, remaining):
    update = validate_payment_update(total_amount=Decimal(total), payment_status=status)
    assert update.status.value == status
    assert (update.paid_amount, update.refunded_amount, update.remaining_amount) == tuple(map(Decimal, (paid, refunded, remaining)))


@pytest.mark.parametrize("status", ["partially_paid", "partially_refunded", "partial", "unknown", None])
def test_payment_validation_rejects_noncanonical_targets(status):
    with pytest.raises(DomainError) as exc:
        validate_payment_update(total_amount=Decimal("10.00"), payment_status=status)
    assert exc.value.code == "invalid_payment_status"


def test_payment_validation_rejects_negative_invoice_total():
    with pytest.raises(DomainError) as exc:
        validate_payment_update(total_amount=Decimal("-0.01"), payment_status="paid")
    assert exc.value.code == "negative_total_amount"


def test_record_order_activity_stores_stable_snapshots_and_reason(db: Session) -> None:
    order = Order(
        order_number="ORD-ACTIVITY",
        public_token="activity-token",
        customer_name="Customer",
        customer_phone="0590000000",
        address="Address",
        subtotal=Decimal("10.00"),
        total=Decimal("10.00"),
    )
    db.add(order)
    db.flush()
    before = {"unit_price": Decimal("10.00"), "line": {"quantity": 1}}
    after = {"unit_price": Decimal("12.50"), "line": {"quantity": 2}}

    event = record_order_activity(
        db,
        order_id=order.id,
        invoice_id=None,
        actor_admin_id=None,
        event_type="order_item_price_changed",
        before_data=before,
        after_data=after,
        reason="Customer agreed to the change",
    )
    before["line"]["quantity"] = 99
    after["unit_price"] = Decimal("0.00")
    db.commit()
    db.expire_all()

    saved = db.get(type(event), event.id)
    assert saved.before_data == {"unit_price": "10.00", "line": {"quantity": 1}}
    assert saved.after_data == {"unit_price": "12.50", "line": {"quantity": 2}}
    assert saved.reason == "Customer agreed to the change"


def test_record_order_activity_redacts_unknown_and_nested_secret_data(db: Session) -> None:
    order = Order(
        order_number="ORD-ACTIVITY-SECRETS",
        public_token="activity-secrets-token",
        customer_name="Customer",
        customer_phone="0590000000",
        address="Address",
        subtotal=Decimal("10.00"),
        total=Decimal("10.00"),
    )
    db.add(order)
    db.flush()

    event = record_order_activity(
        db,
        order_id=order.id,
        invoice_id=None,
        actor_admin_id=None,
        event_type="payment_updated",
        before_data={
            "paid_amount": Decimal("1.00"),
            "api_token": "top-secret",
            "context": {"authorization": "Bearer secret", "api_key": "nested-secret"},
        },
        after_data={"refresh_token": "new-secret", "payment_status": "partial"},
        reason="Payment recorded",
    )
    db.commit()
    db.expire_all()

    saved = db.get(type(event), event.id)
    assert saved.before_data == {
        "paid_amount": "1.00",
        "api_token": "[redacted]",
        "context": {"authorization": "[redacted]", "api_key": "[redacted]"},
    }
    assert saved.after_data == {"refresh_token": "[redacted]", "payment_status": "partial"}


def test_order_activity_rows_reject_updates_and_deletes_after_insert(db: Session) -> None:
    order = Order(
        order_number="ORD-ACTIVITY-IMMUTABLE",
        public_token="activity-immutable-token",
        customer_name="Customer",
        customer_phone="0590000000",
        address="Address",
        subtotal=Decimal("10.00"),
        total=Decimal("10.00"),
    )
    db.add(order)
    db.flush()
    event = record_order_activity(
        db,
        order_id=order.id,
        invoice_id=None,
        actor_admin_id=None,
        event_type="created",
        before_data=None,
        after_data={"status": "new"},
        reason=None,
    )
    db.commit()

    event.reason = "tampered"
    with pytest.raises(DomainError, match="immutable"):
        db.commit()
    db.rollback()

    db.delete(event)
    with pytest.raises(DomainError, match="immutable"):
        db.commit()
    db.rollback()


def test_create_order_calculates_domain_totals_and_records_a_creation_activity(
    db: Session, category
) -> None:
    product = make_product(db, category_id=category.id, price="1.005")

    order = orders_service.create_order(
        db,
        orders_service.OrderDraft(
            customer_name="Customer",
            customer_phone="0590000000",
            address="Address",
            items=[(product.id, None, 3)],
        ),
    )

    assert order.subtotal == Decimal("3.00")
    assert order.total == Decimal("3.00")
    assert [(event.event_type, event.after_data) for event in order.activities] == [
        ("order_created", {"status": order.status, "total_amount": "3.00"})
    ]


def test_completion_records_activity_and_invoice_uses_validated_payment_amounts(
    db: Session, category, normal_admin
) -> None:
    product = make_product(db, category_id=category.id, price="10.00")
    order = orders_service.create_order(
        db,
        orders_service.OrderDraft(
            customer_name="Customer",
            customer_phone="0590000000",
            address="Address",
            items=[(product.id, None, 1)],
        ),
    )

    orders_service.complete_order(
        db,
        order_id=order.id,
        payment_method="cash_on_delivery",
        payment_status="unpaid",
        payment_details=None,
        invoice_notes=None,
        admin=normal_admin,
    )
    invoice = invoices_service.get_for_order(db, order.id)

    assert invoice is not None
    assert invoice.payment_status == PaymentStatus.UNPAID.value
    assert invoice.paid_amount == Decimal("0.00")
    assert invoice.refunded_amount == Decimal("0.00")
    assert invoice.remaining_amount == Decimal("10.00")
    assert any(event.event_type == "order_completed" for event in order.activities)
    invoice_event = next(event for event in order.activities if event.event_type == "invoice_issued")
    assert invoice_event.actor_admin_id == normal_admin.id


def test_invoice_issuer_snapshot_survives_admin_profile_changes(
    db: Session, category, normal_admin
) -> None:
    product = make_product(db, category_id=category.id, price="10.00")
    order = orders_service.create_order(
        db,
        orders_service.OrderDraft(
            customer_name="Customer",
            customer_phone="0590000000",
            address="Address",
            items=[(product.id, None, 1)],
        ),
    )
    orders_service.complete_order(
        db,
        order_id=order.id,
        payment_method="cash_on_delivery",
        payment_status="unpaid",
        payment_details=None,
        invoice_notes=None,
        admin=normal_admin,
    )
    db.commit()

    normal_admin.full_name = "Renamed Admin"
    normal_admin.email = "renamed@example.com"
    db.commit()
    db.expire_all()

    invoice = invoices_service.get_for_order(db, order.id)
    assert invoice is not None
    assert invoice.issued_by_admin_id == normal_admin.id
    assert invoice.issued_by_admin_name == "Test Admin"
    assert invoice.issued_by_admin_email == "admin@example.com"


def test_failed_completion_cannot_be_committed_as_a_partial_order(
    db: Session, category, normal_admin
) -> None:
    product = make_product(db, category_id=category.id, price="10.00")
    order = orders_service.create_order(
        db,
        orders_service.OrderDraft(
            customer_name="Customer",
            customer_phone="0590000000",
            address="Address",
            items=[(product.id, None, 1)],
        ),
    )
    db.commit()

    with pytest.raises(DomainError, match="Select unpaid, paid or refunded") as exc:
        orders_service.complete_order(
            db,
            order_id=order.id,
            payment_method="cash_on_delivery",
            payment_status="partially_paid",
            payment_details=None,
            invoice_notes=None,
            admin=normal_admin,
        )
    db.commit()
    db.expire_all()

    assert exc.value.code == "invalid_payment_status"
    saved = db.get(Order, order.id)
    assert saved.status != "completed"
    assert saved.is_locked is False
    assert invoices_service.get_for_order(db, order.id) is None
