from __future__ import annotations

import logging
from types import SimpleNamespace

from app.api.v1.endpoints import public_checkout
from app.core.config import settings
from app.models import Order
from app.services import whatsapp_notifications
from tests.conftest import make_product


def _enable_whatsapp(monkeypatch) -> None:
    values = {
        "WHATSAPP_NOTIFICATIONS_ENABLED": True,
        "WHATSAPP_GRAPH_API_VERSION": "v99.0",
        "WHATSAPP_ACCESS_TOKEN": "test-secret-access-token",
        "WHATSAPP_PHONE_NUMBER_ID": "123456789",
        "WHATSAPP_NOTIFICATION_RECIPIENT": "+970 59 123 4567",
        "WHATSAPP_ORDER_TEMPLATE": "new_order_notification",
        "WHATSAPP_ORDER_TEMPLATE_LANGUAGE": "ar",
        "WHATSAPP_NOTIFICATION_TIMEOUT_SECONDS": 8,
        "PUBLIC_BASE_URL": "https://store.example",
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


def _order_payload(product, *, reference="whatsapp-notification-ref") -> dict:
    return {
        "client_reference": reference,
        "customer_name": "سارة أحمد",
        "customer_phone": "0591234567",
        "address": "رام الله، شارع الإرسال، بناية ٥",
        "items": [{"product_id": product.id, "quantity": 2}],
    }


def test_checkout_schedules_notification_once_and_only_after_commit(
    client, db, session_factory, monkeypatch,
):
    product = make_product(db)
    scheduled: list[int] = []

    def observe_schedule(_background_tasks, order):
        # A completely separate Session can already see the row.  This proves the
        # notification seam is reached only after the commerce commit.
        with session_factory() as verify:
            persisted = verify.get(Order, order.id)
            assert persisted is not None
            assert persisted.order_number == order.order_number
        scheduled.append(order.id)

    monkeypatch.setattr(
        public_checkout.whatsapp_notifications,
        "add_order_created_task",
        observe_schedule,
    )

    payload = _order_payload(product)
    first = client.post("/api/v1/orders", json=payload)
    assert first.status_code == 201, first.text
    retry = client.post("/api/v1/orders", json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert scheduled == [first.json()["id"]]


def test_whatsapp_template_contains_committed_order_summary(
    client, db, monkeypatch,
):
    _enable_whatsapp(monkeypatch)
    product = make_product(db, price="70.00")
    sent: list[tuple[str, dict]] = []

    def capture(url: str, payload: dict) -> None:
        sent.append((url, payload))

    monkeypatch.setattr(whatsapp_notifications, "_post_json", capture)

    response = client.post("/api/v1/orders", json=_order_payload(product, reference="wa-summary"))
    assert response.status_code == 201, response.text
    assert len(sent) == 1

    url, payload = sent[0]
    assert url == "https://graph.facebook.com/v99.0/123456789/messages"
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "970591234567"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "new_order_notification"
    assert payload["template"]["language"] == {"code": "ar"}

    values = [
        parameter["text"]
        for parameter in payload["template"]["components"][0]["parameters"]
    ]
    created = response.json()
    assert values == [
        created["order_number"],
        "سارة أحمد",
        "970591234567",
        "غير محددة",
        "2",
        "140.00",
        f"https://store.example/admin/orders/{created['id']}",
    ]


def test_checkout_retry_does_not_send_duplicate_whatsapp(
    client, db, monkeypatch,
):
    _enable_whatsapp(monkeypatch)
    product = make_product(db)
    sent: list[dict] = []
    monkeypatch.setattr(
        whatsapp_notifications,
        "_post_json",
        lambda _url, payload: sent.append(payload),
    )
    payload = _order_payload(product, reference="wa-idempotent")

    first = client.post("/api/v1/orders", json=payload)
    retry = client.post("/api/v1/orders", json=payload)

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]
    assert len(sent) == 1


def test_disabled_notifications_never_call_meta(client, db, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_NOTIFICATIONS_ENABLED", False)
    product = make_product(db)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Meta request must not run while notifications are disabled")

    monkeypatch.setattr(whatsapp_notifications, "_post_json", unexpected)
    response = client.post(
        "/api/v1/orders",
        json=_order_payload(product, reference="wa-disabled"),
    )
    assert response.status_code == 201, response.text
    assert db.query(Order).count() == 1


def test_provider_failure_is_contained_and_secrets_are_not_logged(
    client, db, monkeypatch, caplog,
):
    _enable_whatsapp(monkeypatch)
    product = make_product(db)

    def fail(_url: str, _payload: dict) -> None:
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(whatsapp_notifications, "_post_json", fail)

    with caplog.at_level(logging.ERROR, logger=whatsapp_notifications.__name__):
        response = client.post(
            "/api/v1/orders",
            json=_order_payload(product, reference="wa-provider-failure"),
        )

    assert response.status_code == 201, response.text
    assert db.query(Order).count() == 1
    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert "WhatsApp order notification failed" in combined
    assert settings.WHATSAPP_ACCESS_TOKEN not in combined
    assert settings.WHATSAPP_NOTIFICATION_RECIPIENT not in combined


def test_build_order_notification_is_an_immutable_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://store.example")
    order = SimpleNamespace(
        id=41,
        order_number="ORD-TEST-41",
        customer_name="Customer",
        customer_phone="970591234567",
        delivery_area_name="نابلس",
        total=150,
        items=[SimpleNamespace(quantity=1), SimpleNamespace(quantity=3)],
    )

    notification = whatsapp_notifications.build_order_notification(order)

    assert notification.order_id == 41
    assert notification.item_count == 4
    assert notification.total == "150.00"
    assert notification.admin_url == "https://store.example/admin/orders/41"
