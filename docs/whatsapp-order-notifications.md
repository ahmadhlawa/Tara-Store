# WhatsApp order notifications

TARA can send a best-effort WhatsApp notification to the store owner after a new
website order has been committed successfully.

This is notification-only integration. It does not provide a chatbot, customer
replies, order management from WhatsApp, or automated status changes.

## Delivery semantics

The checkout transaction remains the source of truth.

1. The backend validates and creates the order.
2. The database transaction commits.
3. Only when the request created a genuinely new order, the backend schedules one
   background notification.
4. The HTTP response is returned independently of Meta delivery.
5. Provider/network failures are logged without credentials and never roll back,
   duplicate, or invalidate the committed order.

The existing checkout idempotency key (`client_reference`) is also respected: a
retry that returns an existing order does not schedule another notification.

This implementation uses FastAPI in-process background tasks. It is intentionally
lightweight and best-effort. A process crash after the database commit and before
the background task runs can lose a notification. If durable retries are needed
later, replace this with an outbox/queue without changing the checkout contract.

## Meta template

Use an approved WhatsApp template with seven body parameters in this exact order:

1. order number
2. customer name
3. customer phone
4. delivery area
5. total item quantity
6. order total
7. direct Admin order URL

Example body:

```text
طلب جديد {{1}}
الزبون: {{2}}
الهاتف: {{3}}
المنطقة: {{4}}
عدد القطع: {{5}}
الإجمالي: {{6}} ₪
عرض الطلب: {{7}}
```

The template name must use lowercase letters, digits, and underscores.

## Environment

```dotenv
WHATSAPP_NOTIFICATIONS_ENABLED=false
WHATSAPP_GRAPH_API_VERSION=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_NOTIFICATION_RECIPIENT=
WHATSAPP_ORDER_TEMPLATE=
WHATSAPP_ORDER_TEMPLATE_LANGUAGE=ar
WHATSAPP_NOTIFICATION_TIMEOUT_SECONDS=8
```

`WHATSAPP_GRAPH_API_VERSION` is deliberately not hard-coded. Set it to the
currently supported Meta Graph API version used by the WhatsApp Business account,
for example in the `vNN.N` form documented by Meta.

`WHATSAPP_NOTIFICATION_RECIPIENT` is the owner's international WhatsApp number.
Common separators and a leading plus are tolerated; only digits are sent to Meta.

`PUBLIC_BASE_URL` must also be set so the notification can link directly to:

```text
/admin/orders/<order-id>
```

Keep notifications disabled in local development unless intentionally exercising a
real Meta test/sandbox sender.

## Security

- The access token belongs only in the untracked backend environment.
- The token and recipient number are never logged.
- Provider response bodies are not logged.
- The browser never receives Meta credentials.
- No WhatsApp request is made when notifications are disabled.
