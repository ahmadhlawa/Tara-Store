# Full admin and storefront validation

Acceptance run for the integration of `feat/order-invoice-workflow` into `main`.

| | |
| --- | --- |
| Date | 2026-08-05 |
| Pre-merge `main` | `c9d6b1e` |
| Feature head | `800af5a` |
| Merge commit | `f34ac40` (no conflicts) |
| Safety tag | `backup-main-before-order-invoice-20260805-173713` |
| Browser | Microsoft Edge (installed Chromium channel) via Playwright |
| Viewports | 1440x900, 768x1024, 390x844 |
| Frontend | `http://localhost:5173` (Vite dev server, from `main`) |
| Backend | `http://127.0.0.1:8000` (uvicorn, from `main`) |
| Database | disposable `backend/data/vista_full_validation_20260805-183827.db` at `0009_invoice_issuer_snapshot` |

The original `vista_preview.db` was copied, never modified. Its SHA-256 was
`6335E1EA841D1136289E59D7975C7FB64F0051C8DDBBBD9246757F59FD312E9A` before the run and
unchanged after the copy was taken.

## Automated results

| Suite | Result |
| --- | --- |
| Backend `pytest -q` | 374 tests: **370 passed, 4 xfailed**, 0 failed, 0 skipped |
| Frontend `vitest run` | 14 files, **149 passed** (was 147; +2 from the checkout fix) |
| Frontend `vite build` | success, 121 modules, 409 kB JS / 67 kB CSS |
| Browser acceptance | **115 passed, 0 failed** (12 smoke + 42 routes + 10 journeys + 51 responsive) |

The four xfails are exactly the four that existed before the merge, all in
`tests/test_order_invoice_remediation.py`, all documenting the same absent contract: no
revision-token or ETag exists on the admin API, so a stale-write test cannot be written
against it. None of them hides an idempotency, invoice-uniqueness, rollback, race,
permission or active-invoice failure — those are covered by passing tests elsewhere. No
new xfail, skip or weakened assertion was introduced.

The only warning across the whole backend run is a `StarletteDeprecationWarning` about
`httpx` in FastAPI's own TestClient — third-party, unrelated to this work.

### Migrations

Verified on throwaway copies, both directions:

| Path | Result |
| --- | --- |
| `0003_invoices` → head | `0009_invoice_issuer_snapshot` |
| `0003_invoices` → head → `0003_invoices` → head | returns to head cleanly |
| `0004_import_batches` → head | `0009_invoice_issuer_snapshot` |
| `0004_import_batches` → head → `0004_import_batches` → head | returns to head cleanly |
| real runtime data (`vista_preview.db` copy at `0004`) → head | upgraded, all rows intact |

## Route coverage

Every route both routers declare was opened in the browser and asserted to render with
**no console error and no failed network request**.

| Surface | Declared | Walked | Passed |
| --- | --- | --- | --- |
| Public routes | 21 | 21 | 21 |
| Admin routes | 21 | 21 | 21 |

Public: `/`, `/shop`, `/offers`, `/packages`, `/molds`, `/search`, `/category/:slug`,
`/product/:slug`, `/cart`, `/checkout`, `/order-success/:orderNumber`, `/blog`,
`/blog/:slug`, `/page/:slug`, `/about`, `/privacy-policy`, `/return-policy`, `/terms`,
`/contact`, `/tools/calculator`, and the 404 fallback.

Admin: login, dashboard, products, product editor, categories, orders, order detail,
manual order, invoices, invoice detail, coupons, delivery, hero, banners, home,
articles, pages, media, settings, admins, audit, and the catch-all redirect.

`/order-success/:orderNumber` is reached through the checkout journey rather than by
direct navigation, because the route is only meaningful for an order that exists.

## Global technical checks

| Check | Result |
| --- | --- |
| Storefront first load: console and network | clean |
| Admin workspace after login: console and network | clean |
| Reload on a nested SPA route (`/admin/invoices`) | session survives |
| Unauthenticated admin route | redirects to `/admin/login` |
| Cleared session | redirects to `/admin/login` |
| Deactivated account login | rejected, Arabic message, no session |
| Anonymous admin API call | 401 |
| Unknown public path | storefront 404, no admin chrome |
| Storefront rendering admin chrome | never |
| Public order tracking link or route | absent |
| Admin-login icon in the header | present and working |

## Integration journeys

| Journey | Result | Evidence |
| --- | --- | --- |
| C — website order lifecycle | pass | Real browser checkout: empty-form submit shows a visible Arabic error; the terms error appears both beside the checkbox and in the form alert; the order posts `201` with `payment_method: bank_transfer`; the browser lands on `/order-success/<number>`; the WhatsApp hand-off is attempted **after** persistence and was blocked by the test; the cart is empty afterwards; the admin list finds **exactly one** order, `source=website`, `payment_status=unpaid`; the order detail screen shows it. |
| D — manual order lifecycle | pass | Mixed catalog + manual order posts `201` to `/admin/orders/manual` — no 405, no 422. Incomplete save issues **no** invoice. The manual line creates **no** catalog product. Completing at creation issues **exactly one** active invoice carrying the issuer snapshot (name and email). Completing again is idempotent (`200`) and mints no second invoice; the first invoice's method, paid amount and total are unchanged. |
| E — invoice archive filters | pass | All 3 invoice statuses, all 5 payment statuses and all 6 sources return `200`. Seven combinations return `200`, including `replaced + partially_paid`, `active + paid`, `source + date range`, `search + payment`, and an inverted date range (empty result, not an error). Driving every select on the screen through every option produces no client-side error and never the invalid-data message. |
| H — permission boundaries | pass | A normal admin is redirected away from `/admin/orders/manual`, `/admin/admins` and `/admin/audit` in the browser, **and** refused by the API: `403` on `GET /admin/admins`, `403` on `GET /admin/audit-logs`, `403` on `POST /admin/orders/manual`. Hidden navigation was not accepted as the boundary. A normal admin cannot refund or lower a paid amount. A super admin reaches all three screens. |

## Responsive, RTL and accessibility

51 checks across the three viewports:

- No page scrolls the document horizontally at 1440, 768 or 390 — public or admin.
- `direction: rtl` on every page checked, public and admin.
- Header cart control and admin-login control carry accessible names and stay reachable.
- Every visible input, select and textarea on the checkout form has an accessible name.
- The admin login form completes with the keyboard alone (Tab and Enter).

## Defects found and fixed

### 1. Checkout offered a payment value the API rejects

- **Reproduction.** Open `/checkout`, choose "تحويل بنكي / يدوي", complete the form,
  submit. Confirmed directly against the running API: `POST /api/v1/orders` with
  `payment_method: "manual"` returns **HTTP 422**.
- **Root cause.** `frontend/src/store.js` declared the option with `key: "manual"`,
  while the API's `PaymentMethod` enum is `cash_on_delivery | card | bank_transfer`.
  The customer lost the order after filling the whole form.
- **Files.** `frontend/src/store.js`, `frontend/src/pages/CheckoutRoutePage.jsx`.
- **Fix direction.** The frontend was corrected to `bank_transfer`. The backend enum was
  deliberately **not** widened to accept a wrong value, and no duplicate route was added.
- **Test.** `frontend/src/test/checkout.test.js` now asserts every offered payment key
  against the enum, and that each has a label. Confirmed red before the fix
  (`unsupported payment key "manual"`), green after.
- **Commit.** `1c49d98`.
- **Browser re-test.** Journey C selects that exact option and asserts the created order
  comes back with `payment_method: "bank_transfer"`.

## Findings that are not defects

- **`InvoiceStatus.CANCELLED` is unreachable through the API.** An invoice exists only
  once its order is completed, and `POST /admin/invoices/{number}/cancel` then refuses
  with `order_locked` — asserted on purpose by the backend suite. The archive still
  offers `cancelled` as a filter for rows written before completion locked orders. This
  is consistent, but it means invoice cancellation cannot be exercised from the invoice
  screen today. The fixture writes one such row directly and labels it as legacy.
- **Repeated completion returns `200`, not an error.** `complete_order` returns the
  order untouched when an invoice already exists. This is deliberate idempotency and the
  invariant that matters — one active invoice, unchanged snapshot — holds.
- **The runtime database was two revisions behind the code.** `vista_preview.db` was at
  `0004_import_batches` while the merged code needs `0009`. See the note below.

## Action required before normal development

`backend/data/vista_preview.db` is still at `0004_import_batches`. Merged `main` needs
`0009_invoice_issuer_snapshot`, so the order and invoice screens will fail against it
until it is upgraded. It was deliberately left untouched by this run:

```powershell
cd D:\Project\vista-store-e-commerce\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Coverage this run did not reach

Stated plainly rather than implied:

- **Per-control CRUD on the content and catalog admin screens.** Every admin screen was
  opened, asserted to render cleanly and checked for layout and RTL, and the orders,
  manual-order, invoice and permission surfaces were driven through their real
  workflows. Exhaustive create/edit/delete/validation exercising of every field on the
  products, categories, coupons, delivery, hero, banners, home, articles, pages, media
  and settings editors was **not** performed in the browser; those screens are covered
  here at the render, layout and permission level only.
- **Dashboard figures were not reconciled against the database** row by row.
- **Coupon and delivery-fee arithmetic at checkout** was not asserted end to end in the
  browser; the fixture contains the data for it and the API accepts the codes.
- **Simulated backend-unavailable, 500 and expired-session paths** were not driven in
  the browser. The existing unit suite covers the failed-order path (the cart is kept
  and WhatsApp is not opened).
- **MySQL downgrade ordering** was not exercised; only SQLite was available locally.

## Development validation (2026-08-07)

This is local development validation against mock/demo data, not production or staging
certification. It is not an exhaustive button, field, modal, or filter inventory. The
accepted frontend baseline is 149/149 unit tests and a Vite 6.4.3
production build (121 modules), both exit 0. Backend evidence is 384 passed, four
approved xfailed, and zero failures/errors. MySQL upgrade/downgrade/re-upgrade and
SQLite 0004-to-0009 migration evidence are recorded in their respective validation
notes.

| Spec | Result | Evidence actually asserted |
| --- | --- | --- |
| `promotions-delivery.spec.js` | 1 passed | Real cart coupon, delivery selection, and browser checkout total sourced from the pricing API; no order is created. |
| `admin-catalog-lifecycle.spec.js` | 2 passed | Unique create/edit/public visibility/deactivate/reactivate/delete lifecycle plus `422 validation_error` for invalid numeric input. |

The checks below establish critical lifecycle evidence; they do not claim exhaustive
control-by-control QA.

## Final focused regression (2026-08-07)

One complete suite was run against `http://localhost:5175` and
`http://127.0.0.1:8001`, with durable output in
`%TEMP%/vista-final-playwright-20260807.log`.

| Total | Passed | Failed | Skipped | Flaky/retries | Duration |
| --- | --- | --- | --- | --- | --- |
| 128 | 102 | 26 | 0 | 0 | 10m 30s |

It used Playwright 1.62.1 and the installed Edge Chromium channel: desktop 93, tablet
18, mobile 17. Exit was 1. The 26 failures are media 404s, not distinct workflow
assertion failures: the 8001 process served its default `vista-uploads` directory rather
than the disposable fixture's `vista_full_validation_20260806-041041_uploads` directory.
This isolated disposable-fixture configuration issue does not block normal development.
Production/staging browser and media validation remains future work after real data,
hosting, and storage infrastructure are integrated.

The canonical runtime remains `http://localhost:5173` → `http://127.0.0.1:8000`, using
`backend/data/vista_preview.db` at `0009_invoice_issuer_snapshot`; it was not modified.

Environment inspection found no existing preview-admin credential supplied through the
local environment or configuration. Authenticated canonical preview-admin smoke could
not be performed because no usable existing preview credential was available;
authenticated admin behavior is covered against the isolated disposable validation DB.

### Critical release checklist

| Workflow | Status | Evidence |
| --- | --- | --- |
| Authentication/login/logout | PASS | `smoke.spec.js`; `test_auth.py` |
| Inactive admin denial | PASS | `smoke.spec.js`; `test_auth.py` |
| API role authorization | PASS | `journeys.spec.js`; `test_auth.py` |
| Product CRUD/public reflection | PASS | `admin-catalog-lifecycle.spec.js`; `test_catalog.py` |
| Category CRUD/public reflection | PASS | category lifecycle; `test_catalog.py` |
| Coupon arithmetic | PASS | `promotions-delivery.spec.js`; `test_checkout.py` |
| Delivery arithmetic | PASS | `promotions-delivery.spec.js`; `test_checkout.py` |
| Public checkout to admin order | PASS | `journeys.spec.js` |
| Website order lifecycle | PASS | `journeys.spec.js`; `test_admin_order_edit.py` |
| Manual/mixed order lifecycle | PASS | `journeys.spec.js`; `test_admin_order_edit.py` |
| Duplicate-write prevention | PASS | `test_invoices.py`; `test_order_invoice_remediation.py` |
| Invoice on completion | PASS | `journeys.spec.js`; `test_invoices.py` |
| One active invoice/replacement | PASS | `test_invoices.py`; `test_order_invoice_persistence.py` |
| Invoice payment state | PASS | `test_invoices.py`; `test_order_invoice_domain.py` |
| Server-side validation | PASS | `admin-catalog-lifecycle.spec.js`; backend tests |
| Public/admin publication | PASS | ResourceScreen lifecycle; `test_content_and_media.py` |
| Desktop/tablet/mobile usability | PASS | previously accepted responsive/browser baseline |
| Missing public/tracking route | PASS | `smoke.spec.js`; `routes.spec.js` |
| Anonymous protected API denial | PASS | `smoke.spec.js`; `test_auth.py` |

Category defect: a blank optional `parent_id` was sent as `""` and received 422. The
category field now opts into existing `emptyAsNull` serialization; the dedicated browser
regression proves a null POST, 201, refresh persistence, and deletion. Commit:
`b69568b fix(admin): normalize empty category parent selection`.

The authenticated canonical preview-admin smoke remains unavailable because no usable
existing preview credential was supplied. No credential or preview database was changed.

This document must not be used as a production-readiness, deployment, Cloudflare, or
final-media-storage certificate.
