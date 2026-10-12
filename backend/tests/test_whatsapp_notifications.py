from __future__ import annotations

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
        "WHATSAPP_CUSTOMER_ORDER_TEMPLATE": "tara_order_received",
        "WHATSAPP_CUSTOMER_ORDER_TEMPLATE_LANGUAGE": "ar",
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
    assert payload["template"]["name"] == "tara_order_received"
    assert payload["template"]["language"] == {"code": "ar"}

    values = [
        parameter["text"]
        for parameter in payload["template"]["components"][0]["parameters"]
    ]
    created = response.json()
    assert values == [
        created["order_number"],
        "970591234567",
        "رام الله، شارع الإرسال، بناية ٥",
        "• منتج اختبار × 2 — 140.00 ₪",
        "140.00",
        "0.00",
        "0.00",
        "140.00",
    ]


def test_each_order_targets_its_customer_phone(client, db, monkeypatch):
    _enable_whatsapp(monkeypatch)
    product = make_product(db)
    sent: list[dict] = []
    monkeypatch.setattr(
        whatsapp_notifications,
        "_post_json",
        lambda _url, payload: sent.append(payload),
    )

    first = client.post(
        "/api/v1/orders",
        json=_order_payload(product, reference="wa-customer-one"),
    )
    second_payload = _order_payload(product, reference="wa-customer-two")
    second_payload["customer_phone"] = "0521234567"
    second = client.post("/api/v1/orders", json=second_payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert [payload["to"] for payload in sent] == [
        "970591234567",
        "972521234567",
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
    client, db, monkeypatch,
):
    _enable_whatsapp(monkeypatch)
    product = make_product(db)

    def fail(_url: str, _payload: dict) -> None:
        raise RuntimeError("simulated provider failure")

    logged: list[tuple[str, tuple[object, ...]]] = []

    def capture_error(message: str, *args: object, **_kwargs: object) -> None:
        logged.append((message, args))

    monkeypatch.setattr(whatsapp_notifications, "_post_json", fail)
    monkeypatch.setattr(whatsapp_notifications.logger, "error", capture_error)

    response = client.post(
        "/api/v1/orders",
        json=_order_payload(product, reference="wa-provider-failure"),
    )

    assert response.status_code == 201, response.text
    assert db.query(Order).count() == 1
    assert len(logged) == 1
    message, args = logged[0]
    assert "WhatsApp order notification failed" in message
    rendered_inputs = " ".join([message, *(str(arg) for arg in args)])
    assert settings.WHATSAPP_ACCESS_TOKEN not in rendered_inputs
    assert "970591234567" not in rendered_inputs


def test_build_order_notification_is_an_immutable_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://store.example")
    order = SimpleNamespace(
        id=41,
        order_number="ORD-TEST-41",
        customer_phone="970591234567",
        address="نابلس، شارع فيصل",
        subtotal=150,
        discount=10,
        delivery_fee=20,
        packaging_type="gift",
        packaging_fee=5,
        total=165,
        items=[
            SimpleNamespace(
                product_name="شمعة",
                variant_description="لافندر",
                quantity=1,
                line_total=50,
            ),
            SimpleNamespace(
                product_name="وسادة",
                variant_description=None,
                quantity=2,
                line_total=100,
            ),
        ],
    )

    notification = whatsapp_notifications.build_order_notification(order)

    assert notification.order_id == 41
    assert notification.customer_phone == "970591234567"
    assert notification.address == "نابلس، شارع فيصل"
    assert notification.items_summary == (
        "• شمعة · لافندر × 1 — 50.00 ₪\n"
        "• وسادة × 2 — 100.00 ₪\n"
        "• تغليف كهدية — 5.00 ₪"
    )
    assert notification.subtotal == "150.00"
    assert notification.discount == "10.00"
    assert notification.delivery_fee == "20.00"
    assert notification.total == "165.00"
