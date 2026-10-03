# Tara Analytics Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the existing Admin analytics into a compact aggregate dashboard with average session duration, clean location/product charts, a checkout funnel, completed-checkout count, and abandoned-cart metric without per-person surveillance.

**Architecture:** Extend the existing anonymous analytics-session model with the minimum funnel events tied only to `AnalyticsSession`. Keep current visit/product-view privacy controls, cookies, same-origin checks, bot filtering, trusted Cloudflare location handling, request locking, and rate limiting. The Admin summary aggregates today/7d/30d data; the UI displays each dataset once using existing React/CSS rather than a new chart dependency.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, Vitest, Pytest, SQLite, MySQL 8.

**Spec:** `docs/superpowers/specs/2026-10-03-tara-customer-change-batch-design.md`

## Global Constraints

- No individual-session rows or drill-down in Admin.
- No IP persistence.
- No customer name, email, phone, address, or order contents in analytics events.
- Preserve current approximate location behavior exactly; do not reopen location-infrastructure work.
- Preserve same-origin validation, trusted Cloudflare proxy token/headers, bot filtering, analytics cookies, locking, and rate limits.
- Periods remain: today, last 7 days, last 30 days.
- Show visitor locations once and most-viewed products once; remove duplicated top-product presentation.
- Funnel stages: product view → add to cart → checkout reached → order completed.
- For analytics only, `order_completed` means successful website checkout/order creation, not later fulfillment status `completed`.
- New funnel history begins at deployment; do not fabricate historical events from old product views.
- Average session duration may use existing `started_at` and `last_activity_at` historical data.
- No chart library or new frontend dependency.
- No GitHub push and no Production deployment in this plan.

## Review Focus

- Repeated add-to-cart clicks and React rerenders need a clear counting rule; Task 2 tests one event per actual add action, never per render.
- Successful idempotent order creation must count exactly one `order_completed` event even if the client retries; Task 2 tests it.
- Abandoned carts must exclude sessions that later complete checkout and must only count after a deterministic timeout/window; Task 3 tests it.
- Session duration must never become negative due to malformed timestamps; Task 3 clamps/validates it.
- Analytics failures must never block cart mutation, checkout navigation, or order creation; Task 2 tests fire-and-forget/failure isolation.

---

## File Map

### Backend

- Modify: `backend/app/models/analytics.py` — add minimal generic event model.
- Modify: `backend/app/schemas/analytics.py` — event input and expanded summary output.
- Modify: `backend/app/services/analytics.py` — event recorder and aggregate queries.
- Modify: `backend/app/api/v1/endpoints/analytics.py` — public event endpoint and expanded Admin summary.
- Modify: `backend/app/api/v1/endpoints/public_checkout.py` — reliable server-side successful-order analytics seam if appropriate for exactly-once counting.
- Create: next Alembic migration for analytics event table/indexes.
- Test: `backend/tests/test_analytics.py`, `backend/tests/test_checkout.py`, `backend/tests/test_migrations.py`.

### Frontend

- Modify: `frontend/src/services/analytics.js` — add fire-and-forget `trackAddToCart` and `trackCheckoutReached`; retain visit/product-view helpers.
- Modify: `frontend/src/api/publicApi.js` — public event call.
- Modify: `frontend/src/app/StoreProvider.jsx` — add-to-cart event at actual user action.
- Modify: `frontend/src/pages/CheckoutRoutePage.jsx` — checkout-reached event with deterministic dedupe.
- Modify: `frontend/src/admin/pages/AnalyticsPage.jsx` — compact cards, single location chart, single top-products chart, funnel, abandoned metric.
- Modify: `frontend/src/api/adminApi.js` only as required for expanded summary shape.
- Test: `frontend/src/test/analytics.test.jsx` plus cart/checkout tests.

---

### Task 1: Persist Minimal Anonymous Funnel Events

**Interfaces:**
- New event types: `add_to_cart`, `checkout_reached`, `order_completed`.
- Existing `AnalyticsProductView` remains funnel stage 1.
- New event rows contain session ID, event type, timestamp, and only minimal anonymous metadata if strictly required for dedupe.

- [ ] **Step 1: Write failing model/API/migration tests**
  - An anonymous existing analytics session can store each approved event type.
  - Unsupported event type is rejected.
  - Event schema has no customer PII/IP fields.
  - Existing same-origin, bot filtering, rate limiting, cookie/session resolution, and lock path are reused.
  - Migration creates indexes supporting event-type/time and session/time aggregation.

- [ ] **Step 2: Run focused tests and verify failure**
  - Run: `cd backend && pytest tests/test_analytics.py tests/test_migrations.py -q`

- [ ] **Step 3: Add `AnalyticsEvent` model and migration**
  - Prefer one generic table because all three new stages share lifecycle and aggregation behavior.
  - Keep schema minimal; do not snapshot cart/customer/order data.
  - Generate the next migration from the actual current head and support SQLite/MySQL 8.

- [ ] **Step 4: Add event recorder and endpoint**
  - Resolve/touch the existing anonymous analytics session using the current trusted path.
  - Use the existing request protections and analytics rate limit.
  - Return normal analytics cookies/context as the existing endpoints do.

- [ ] **Step 5: Run backend tests**

- [ ] **Step 6: Commit locally**
  - `git commit -m "feat: track anonymous checkout funnel events"`

---

### Task 2: Wire Storefront Funnel Events Reliably

**Interfaces:**
- `trackAddToCart()` and `trackCheckoutReached()` are non-blocking/fire-and-forget.
- `order_completed` should be recorded server-side at the successful idempotent order-creation seam if possible, so browser retries cannot double-count.

- [ ] **Step 1: Write failing frontend/backend tests**
  - One actual Add-to-Cart action records one add event.
  - A component rerender records no add event.
  - Checkout page entry records `checkout_reached` according to one documented dedupe rule.
  - Analytics API failure does not prevent the cart from updating or checkout from proceeding.
  - Successful website order creation records exactly one `order_completed` event for its analytics session.
  - Repeating the same idempotent order request/client reference does not add another completion event.

- [ ] **Step 2: Run focused tests and verify failure**

- [ ] **Step 3: Extend frontend analytics helpers**
  - Follow existing `publicApi...catch(() => null)` behavior.
  - Never send customer fields.

- [ ] **Step 4: Hook add-to-cart and checkout-reached**
  - Trigger add event only after a valid actual cart-add action in `StoreProvider`.
  - Trigger checkout reached from checkout page lifecycle with an explicit guard/dedupe; document whether dedupe is per active analytics session or per page mount and test it.

- [ ] **Step 5: Hook successful order completion server-side**
  - Use the request/session context available during public order creation.
  - Tie event creation to the idempotent success path so a repeated client reference returns the existing order without counting a second completion.
  - Analytics recording failure must not roll back a valid commerce order; implement this separation deliberately and test it.

- [ ] **Step 6: Run frontend and backend tests**

- [ ] **Step 7: Commit locally**
  - `git commit -m "feat: wire storefront analytics funnel"`

---

### Task 3: Aggregate Summary Metrics

**Interfaces:**
Expanded `AnalyticsSummaryOut` provides at least:
- `sessions`
- `unique_visitors`
- `average_session_duration_seconds`
- `completed_orders`
- `top_locations`
- `top_products`
- funnel counts for product views / add-to-cart / checkout reached / order completed
- `abandoned_carts`

- [ ] **Step 1: Write failing aggregation tests**
  - Average duration is the average of `max(0, last_activity_at - started_at)` for sessions in the selected period.
  - Historical sessions can contribute duration even if they predate the new event table.
  - `completed_orders` counts successful website checkout completion events in the selected period.
  - Funnel stages use the same period boundaries.
  - Abandoned definition is deterministic: a session has at least one add-to-cart event, has no order-completed event, and its last activity/event is older than the configured analytics session timeout (or an explicitly documented equivalent abandonment window).
  - A still-active session is not abandoned.
  - Store timezone behavior in `period_bounds` remains correct for today/7d/30d.

- [ ] **Step 2: Run backend analytics tests and verify failure**

- [ ] **Step 3: Implement aggregate queries**
  - Prefer SQL aggregation; do not load all sessions/events into Python.
  - Reuse `period_bounds` and current location/top-product logic.
  - Keep deleted-product snapshots functioning as they do today.

- [ ] **Step 4: Extend `AnalyticsSummaryOut` schema**
  - Use explicit types and stable field names consumed by the Admin UI.

- [ ] **Step 5: Run focused and full backend tests**

- [ ] **Step 6: Commit locally**
  - `git commit -m "feat: expand analytics summary metrics"`

---

### Task 4: Simplify Admin Analytics UI

**Interfaces:**
- Consumes expanded aggregate summary only; no per-session endpoint or PII.

- [ ] **Step 1: Write failing frontend analytics tests**
  - Cards render visits, unique visitors, average duration, completed orders.
  - Locations render once as a clear ranked bar chart.
  - Top products render once as a ranked bar chart; the duplicate list is gone.
  - Funnel shows four stages in the approved order.
  - Abandoned carts render as one aggregate metric.
  - today/7d/30d controls remain.
  - No individual visitor/session details are rendered.

- [ ] **Step 2: Run `frontend/src/test/analytics.test.jsx` and verify failure**

- [ ] **Step 3: Refactor `AnalyticsPage.jsx`**
  - Reuse small CSS-bar components and existing Admin design tokens.
  - Remove duplicated product chart + ranking list.
  - Add one location chart and one product chart.
  - Format average duration human-readably while keeping raw seconds in API.
  - Keep responsive layout and accessible labels.

- [ ] **Step 4: Run frontend analytics test, full suite, and build**
  - `cd frontend && npm test`
  - `cd frontend && npm run build`

- [ ] **Step 5: Commit locally**
  - `git commit -m "feat: simplify analytics dashboard"`

---

### Task 5: Batch C Verification

- [ ] Run `cd backend && pytest tests/test_analytics.py tests/test_checkout.py tests/test_migrations.py -q`.
- [ ] Run `cd backend && pytest -q`.
- [ ] Run `cd frontend && npm test`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Run the repository's MySQL 8 gate.
- [ ] Run `git diff --check`.
- [ ] Inspect analytics request schemas/rows and prove there are no name/phone/email/address/IP fields.
- [ ] Verify current location tests pass without changing the accepted location mapping/proxy behavior.
- [ ] Document clearly that funnel and abandoned-cart history begins after deployment.
- [ ] **STOP. Do not push and do not deploy.**
