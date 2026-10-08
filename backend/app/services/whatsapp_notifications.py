"""Best-effort WhatsApp notifications for newly committed website orders.

This module deliberately does not participate in the commerce transaction.  The
checkout endpoint schedules it only after the order commit succeeds.  Delivery is
therefore notification-only: a Meta/API failure must never roll back or alter an
order that the customer already placed.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from urllib import request as urllib_request

from fastapi import BackgroundTasks

from app.core.config import settings
from app.models import Order

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OrderNotification:
    order_id: int
    order_number: str
    customer_name: str
    customer_phone: str
    delivery_area: str
    item_count: int
    total: str
    admin_url: str


def notifications_enabled() -> bool:
    return bool(settings.WHATSAPP_NOTIFICATIONS_ENABLED)


def _recipient_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def build_order_notification(order: Order) -> OrderNotification:
    """Copy only committed, stable values needed by the background task."""
    return OrderNotification(
        order_id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        delivery_area=order.delivery_area_name or "غير محددة",
        item_count=sum(item.quantity for item in order.items),
        total=f"{order.total:.2f}",
        admin_url=f"{settings.PUBLIC_BASE_URL.rstrip('/')}/admin/orders/{order.id}",
    )


def _template_payload(notification: OrderNotification) -> dict:
    """Meta template body parameters, in the documented template order."""
    values = (
        notification.order_number,
        notification.customer_name,
        notification.customer_phone,
        notification.delivery_area,
        str(notification.item_count),
        notification.total,
        notification.admin_url,
    )
    return {
        "messaging_product": "whatsapp",
        "to": _recipient_digits(settings.WHATSAPP_NOTIFICATION_RECIPIENT),
        "type": "template",
        "template": {
            "name": settings.WHATSAPP_ORDER_TEMPLATE.strip(),
            "language": {"code": settings.WHATSAPP_ORDER_TEMPLATE_LANGUAGE.strip()},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in values],
                }
            ],
        },
    }


class _NoRedirect(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post_json(url: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib_request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    # Do not follow redirects while carrying the Meta access token.
    opener = urllib_request.build_opener(_NoRedirect())
    with opener.open(
        http_request, timeout=settings.WHATSAPP_NOTIFICATION_TIMEOUT_SECONDS
    ) as response:
        response.read()


def send_order_notification(notification: OrderNotification) -> bool:
    """Send one template notification and contain every provider/network failure."""
    if not notifications_enabled():
        return False

    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_GRAPH_API_VERSION.strip()}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID.strip()}/messages"
    )
    try:
        _post_json(url, _template_payload(notification))
    except Exception as exc:
        # Never log provider bodies, request headers, tokens, or recipient numbers.
        logger.error(
            "WhatsApp order notification failed; order_id=%s error_type=%s",
            notification.order_id,
            type(exc).__name__,
        )
        return False

    logger.info(
        "WhatsApp order notification sent; order_id=%s order_number=%s",
        notification.order_id,
        notification.order_number,
    )
    return True


def add_order_created_task(background_tasks: BackgroundTasks, order: Order) -> None:
    """Schedule a notification without letting preparation affect checkout."""
    if not notifications_enabled():
        return
    try:
        notification = build_order_notification(order)
        background_tasks.add_task(send_order_notification, notification)
    except Exception as exc:
        logger.error(
            "WhatsApp order notification could not be scheduled; order_id=%s error_type=%s",
            getattr(order, "id", None),
            type(exc).__name__,
        )
