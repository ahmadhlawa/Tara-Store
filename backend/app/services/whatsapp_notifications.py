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
    customer_phone: str
    address: str
    items_summary: str
    subtotal: str
    discount: str
    delivery_fee: str
    total: str


def notifications_enabled() -> bool:
    return bool(settings.WHATSAPP_NOTIFICATIONS_ENABLED)


def _recipient_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _format_items(order: Order) -> str:
    lines = []
    for item in order.items:
        name = item.product_name
        if item.variant_description:
            name = f"{name} · {item.variant_description}"
        lines.append(
            f"• {name} × {item.quantity} — {item.line_total:.2f} ₪"
        )
    return "\n".join(lines)


def build_order_notification(order: Order) -> OrderNotification:
    """Copy only committed, stable values needed by the background task."""
    return OrderNotification(
        order_id=order.id,
        order_number=order.order_number,
        customer_phone=order.customer_phone,
        address=order.address,
        items_summary=_format_items(order),
        subtotal=f"{order.subtotal:.2f}",
        discount=f"{order.discount:.2f}",
        delivery_fee=f"{order.delivery_fee:.2f}",
        total=f"{order.total:.2f}",
    )


def _template_payload(notification: OrderNotification) -> dict:
    """Meta template body parameters, in the documented template order."""
    values = (
        notification.order_number,
        notification.customer_phone,
        notification.address,
        notification.items_summary,
        notification.subtotal,
        notification.discount,
        notification.delivery_fee,
        notification.total,
    )
    return {
        "messaging_product": "whatsapp",
        "to": _recipient_digits(notification.customer_phone),
        "type": "template",
        "template": {
            "name": settings.WHATSAPP_CUSTOMER_ORDER_TEMPLATE.strip(),
            "language": {"code": settings.WHATSAPP_CUSTOMER_ORDER_TEMPLATE_LANGUAGE.strip()},
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
