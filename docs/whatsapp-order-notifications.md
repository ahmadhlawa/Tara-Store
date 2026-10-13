# WhatsApp order notifications

TARA can send a best-effort WhatsApp order-update template to the customer after a
new website order has been committed successfully.

This integration is intentionally narrow. It starts the customer conversation from
the store's WhatsApp Business number so the store owner can continue the
conversation manually. It does not provide a chatbot, automated replies, order
management from WhatsApp, or automated status changes.

## Delivery semantics

The checkout transaction remains the source of truth.

1. The backend validates and creates the order.
2. The database transaction commits.
3. Only when the request created a genuinely new order, the backend schedules one
   background notification.
4. The notification recipient is the committed order's normalized
   `customer_phone`.
5. The HTTP response is returned independently of Meta delivery.
6. Provider/network failures are logged without credentials or customer phone
   numbers and never roll back, duplicate, or invalidate the committed order.

The existing checkout idempotency key (`client_reference`) is also respected: a
retry that returns an existing order does not schedule another notification.

This implementation uses FastAPI in-process background tasks. It is intentionally
lightweight and best-effort. A process crash after the database commit and before
the background task runs can lose a notification. If durable retries are needed
later, replace this with an outbox/queue without changing the checkout contract.

The storefront no longer opens a browser `wa.me` hand-off after checkout. The
message is initiated server-side instead. Checkout displays a short disclosure
beside the customer phone field that order updates will be sent to that number via
WhatsApp.

## Meta template

Use an approved customer-facing Utility template with eight body parameters in
this exact order:

1. order number
2. customer phone
3. delivery address
4. single-line order items summary
5. subtotal
6. discount
7. delivery fee
8. total

Template name:

```text
tara_order_received
```

The approved Arabic body is expected to place those variables as `{{1}}` through
`{{8}}`. Products are sent as one Meta-safe text parameter with items separated
with ` | `, so any number of order items can be represented without changing the
template. Each item includes the snapshotted product name, optional variant,
quantity, and line total. Gift packaging is appended as an extra summary item
only when selected. Every body parameter has all whitespace collapsed to single
spaces, removing newlines, tabs, and repeated spaces.

Do not put Admin URLs, internal notes, or other operator-only values in this
customer template.

## Environment

```dotenv
WHATSAPP_NOTIFICATIONS_ENABLED=false
WHATSAPP_GRAPH_API_VERSION=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_CUSTOMER_ORDER_TEMPLATE=
WHATSAPP_CUSTOMER_ORDER_TEMPLATE_LANGUAGE=ar
WHATSAPP_NOTIFICATION_TIMEOUT_SECONDS=8
```

`WHATSAPP_GRAPH_API_VERSION` is deliberately not hard-coded. Set it to the
supported Meta Graph API version used by the WhatsApp Business account, for
example in the `vNN.N` form documented by Meta.

`WHATSAPP_PHONE_NUMBER_ID` identifies the store's WhatsApp sender. The recipient
is not configured globally: it is taken from each newly committed website order.

The template name must use lowercase letters, digits, and underscores.

Keep notifications disabled in local development unless intentionally exercising a
real Meta test/sandbox sender.

## Security

- The access token belongs only in the untracked backend environment.
- Customer phone numbers are not written to notification logs.
- Provider response bodies are not logged.
- The browser never receives Meta credentials.
- No WhatsApp request is made when notifications are disabled.
