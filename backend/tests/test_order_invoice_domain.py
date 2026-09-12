from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AdminRole, PaymentStatus
from app.models import Order
from app.services import invoices as invoices_service
from app.services import orders as orders_service
from app.services.errors import DomainError, PermissionDeniedError
from app.services.invoices import validate_payment_update
from app.services.orders import calculate_order_totals, record_order_activity
from tests.conftest import make_product


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


@pytest.mark.parametrize(
    ("total", "paid", "refunded", "status", "remaining"),
    [
        ("10.00", "0.00", "0.00", PaymentStatus.UNPAID, "10.00"),
        ("10.00", "4.00", "0.00", PaymentStatus.UNPAID, "6.00"),
        ("10.00", "10.00", "0.00", PaymentStatus.PAID, "0.00"),
        ("10.00", "10.00", "3.00", PaymentStatus.REFUNDED, "3.00"),
        ("10.00", "10.00", "10.00", PaymentStatus.REFUNDED, "10.00"),
    ],
)
def test_payment_validation_derives_status_and_nonnegative_remaining_amount(
    total: str, paid: str, refunded: str, status: PaymentStatus, remaining: str
) -> None:
    update = validate_payment_update(
        total_amount=Decimal(total),
        current_paid_amount=Decimal("0.00"),
        paid_amount=Decimal(paid),
        refunded_amount=Decimal(refunded),
        actor_role=AdminRole.SUPER_ADMIN.value,
        reason="Documented correction" if refunded != "0.00" else None,
    )

    assert update.status == status
    assert update.remaining_amount == Decimal(remaining)


@pytest.mark.parametrize(
    ("total", "paid", "refunded"),
    [
        ("-1.00", "0.00", "0.00"),
        ("10.00", "-0.01", "0.00"),
        ("10.00", "0.00", "-0.01"),
        ("10.00", "10.01", "0.00"),
        ("10.00", "5.00", "5.01"),
    ],
)
def test_payment_validation_rejects_negative_and_out_of_bounds_amounts(
    total: str, paid: str, refunded: str
) -> None:
    with pytest.raises(DomainError):
        validate_payment_update(
            total_amount=Decimal(total),
            current_paid_amount=Decimal("0.00"),
            paid_amount=Decimal(paid),
            refunded_amount=Decimal(refunded),
            actor_role=AdminRole.SUPER_ADMIN.value,
            reason="Documented correction",
        )


def test_routine_admin_cannot_lower_paid_amount_or_record_a_refund() -> None:
    with pytest.raises(PermissionDeniedError):
        validate_payment_update(
            total_amount=Decimal("10.00"),
            current_paid_amount=Decimal("8.00"),
            paid_amount=Decimal("7.00"),
            refunded_amount=Decimal("0.00"),
            actor_role=AdminRole.ADMIN.value,
            reason=None,
        )

    with pytest.raises(PermissionDeniedError):
        validate_payment_update(
            total_amount=Decimal("10.00"),
            current_paid_amount=Decimal("10.00"),
            paid_amount=Decimal("10.00"),
            refunded_amount=Decimal("1.00"),
            actor_role=AdminRole.ADMIN.value,
            reason=None,
        )


@pytest.mark.parametrize("paid,refunded", [("7.00", "0.00"), ("10.00", "1.00")])
def test_super_admin_correction_or_refund_requires_a_nonempty_reason(
    paid: str, refunded: str
) -> None:
    with pytest.raises(DomainError, match="reason"):
        validate_payment_update(
            total_amount=Decimal("10.00"),
            current_paid_amount=Decimal("10.00"),
            paid_amount=Decimal(paid),
            refunded_amount=Decimal(refunded),
            actor_role=AdminRole.SUPER_ADMIN.value,
            reason="  ",
        )


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
        paid_amount=Decimal("0.00"),
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
        paid_amount=Decimal("0.00"),
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

    with pytest.raises(DomainError, match="bounds"):
        orders_service.complete_order(
            db,
            order_id=order.id,
            payment_method="cash_on_delivery",
            paid_amount=Decimal("10.01"),
            payment_details=None,
            invoice_notes=None,
            admin=normal_admin,
        )
    db.commit()
    db.expire_all()

    saved = db.get(Order, order.id)
    assert saved.status != "completed"
    assert saved.is_locked is False
    assert invoices_service.get_for_order(db, order.id) is None
