# Order/Invoice Acceptance Evidence

Date: 2026-08-04

Status: backend/frontend automated acceptance complete; real-browser acceptance is not run in this environment.

## Workflow

- Public `POST /api/v1/orders` requires `client_reference`; retry behavior returns the same persisted order.
- `POST /api/v1/admin/orders/{id}/complete` is the only invoice-issuing path. It completes and locks the order and returns one active invoice; a repeat call keeps that invoice.
- Status changes do not issue invoices. Completed orders cannot be cancelled through the legacy status or invoice-cancel routes; correction uses the super-admin reopen/replacement workflow.
- Invoice payment changes and order activity are retained. Invoice issuer fields are immutable snapshots.

## API and permissions

Endpoints: `POST /api/v1/orders`; `GET/PATCH /api/v1/admin/orders/{id}`; `POST /api/v1/admin/orders/manual`; `POST /api/v1/admin/orders/{id}/complete`; `POST /api/v1/admin/orders/{id}/reopen`; invoice list/detail endpoints; `PATCH /api/v1/admin/invoices/{number}/payment`; `POST /api/v1/admin/invoices/{number}/refund`.

Normal admins may edit incomplete website orders, complete them, and increase payments. Super admins additionally create/edit manual orders, reopen completed orders, and correct/refund payments with a reason. Completed/cancelled orders are locked.

## Migration safety

`tests/test_order_invoice_persistence.py` creates only disposable SQLite databases. It upgrades representative orders and invoices from both `0003_invoices` and `0004_import_batches` to `head`, verifies retained IDs/data and lifecycle backfills, then downgrades only the new chain to `0004_import_batches` and verifies the legacy rows remain. A separate case confirms downgrade refuses replacement-history data instead of deleting invoices.

No original database was upgraded. The worktree has no `backend/data` database or backup files to inspect; the historical paths below are retained as prior evidence only:

- `backend/data/vista_preview.db`: `0004_import_batches`
- `backend/data/vista_store_dev.db`: `0003_invoices`

Timestamped, non-zero backups were created before any potential original upgrade:

- `D:\Project\vista-store-e-commerce\backend\data\vista_preview.db.20260804-051436.bak` (413,696 bytes)
- `D:\Project\vista-store-e-commerce\backend\data\vista_store_dev.db.20260804-051436.bak` (331,776 bytes)

Final head: `0009_invoice_issuer_snapshot`.

Disposable `0003_invoices` and `0004_import_batches` upgrades preserve representative IDs, relationships, line/invoice totals, source/payment snapshots, and invoice rows. Legacy `manual` payment methods normalize to `bank_transfer`. SQLite downgrade to `0004_import_batches` retains records; replacement history refuses downgrade before destructive DDL. MySQL-order unit checks cover the same pre-DDL guard.

## Verification evidence

```text
pytest tests/test_checkout.py tests/test_admin_order_edit.py tests/test_invoices.py tests/test_order_invoice_remediation.py tests/test_order_invoice_domain.py tests/test_order_invoice_persistence.py tests/test_migrations.py
155 passed, 4 xfailed, 1 Starlette/httpx deprecation warning (75.2s)

pytest
367 passed, 0 failed, 4 xfailed, 1 Starlette/httpx deprecation warning (duration was not emitted by this runner)

npm.cmd test
14 files, 134 tests passed

npm.cmd run build
vite production build passed (122 modules)
```

The frontend test command emits existing React Router future-flag warnings and jsdom canvas-not-implemented stderr, but exits successfully.

The four xfails are limited to absent revision-token/ETag stale-write contracts; they do not cover authorization, active-invoice uniqueness, completion idempotency, or rollback. Those rules have non-xfail tests.

Catalog price isolation and manual-item stock/catalog isolation are covered by `test_admin_order_edit.py`; final invoice lines use only persisted order snapshots. Completion/reopen/recompletion tests prove exactly one active invoice per completed order and linked archive history.

## Browser acceptance limitation

The earlier order/invoice run did not execute browser acceptance. The checkout follow-up below supersedes that limitation for the public order-confirmation flow.

## Checkout acceptance follow-up

Root causes: client validation blocked submission when the terms checkbox was unchecked, but only showed a field-local message outside the submit area; the development proxy also defaulted to port 8000 instead of the isolated acceptance backend on 8001.

Reproduction: fill the customer and delivery controls, leave terms unchecked, and press `تأكيد الطلب`. The form received the click, made no order request, and left the submit button unchanged. The fix adds a visible Arabic alert adjacent to the submit button and focuses the first invalid control. The Vite proxy now accepts `VITE_DEV_API_TARGET`, preserving port 8000 as its default; the isolated 5175 process was started with 8001.

Browser evidence: an unchecked agreement produced `يجب الموافقة على الشروط قبل إتمام الطلب`, focused the checkbox, and made zero `POST /api/v1/orders` requests. After agreement, a rapid double-click produced one 201 order request. With the explicitly isolated backend, `ORD-260804-1663` persisted in `vista_browser_acceptance_20260804-154606.db`; the order count changed from 5 to 6 and the server log recorded the same 201.

Verification: focused checkout tests (16), complete `npm.cmd test`, `npm.cmd run build`, and `pytest -q tests/test_checkout.py` all passed.

Original-database note: two earlier exploratory 201 responses were routed through the stale port-8000 proxy rather than the disposable database. They did not affect the disposable DB, so this document cannot attest that the non-isolated target was untouched. No further writes were made to it after this was identified.

## Coupon and delivery expanded browser assertion (2026-08-07)

`frontend/e2e/promotions-delivery.spec.js` verifies fixture coupon `VFXVALID20`
on the 120.00 resin product with the 20.00 Ramallah zone: discount 24.00 and total
116.00 match the checkout browser summary sourced from the pricing API. It creates no
additional order; checkout persistence remains the accepted baseline journey evidence.
The isolated browser media-root 404 is a disposable-fixture configuration issue, not a
production-readiness result; see `full-admin-public-validation.md`.

## Commits and changed files

Commits: `a8dbdfc fix(invoices): preserve payment and issuer snapshots`; `ebf0b75 feat(orders): support typed manager edits for manual orders`; `e6bf762 fix(migrations): harden invoice workflow downgrade safety`.

Changed files are recorded by those commits plus this documentation update; no database, backup, environment, secret, credential, generated-media, or recovery file is staged.

## Manual-order 405 and invoice-filter 422 (2026-08-05)

Two browser defects were reported against the isolated environment: saving on
`/admin/orders/manual` answered `Method Not Allowed`, and invoice-archive filters
answered `البيانات المرسلة غير صالحة.` They have different causes.

### Defect A — manual order returned HTTP 405

Not an application defect. Evidence, in order:

- `POST http://127.0.0.1:8001/api/v1/admin/orders/manual` answers **401**, so the
  route exists and accepts POST on this branch.
- `POST http://localhost:5175/api/v1/admin/orders/manual` — the path the browser
  actually takes — answered **405**.
- The OpenAPI document fetched *through the proxy* had no
  `/api/v1/admin/orders/manual` at all and published `InvoiceStatus` as
  `issued|cancelled`; fetched from 8001 it has the route and
  `active|cancelled|replaced`.

Root cause: `vite.config.js` falls back to `http://127.0.0.1:8000` when
`VITE_DEV_API_TARGET` is unset, and the worktree had no `frontend/.env`. The
5175 dev server was restarted at 21:27 without the variable, so every `/api`
call was proxied to the unrelated pre-branch backend on 8000. There, the POST
fell through to `GET|PATCH /admin/orders/{order_id}` and was refused as 405.
This also produced the legacy `issued` badges in the screenshots — no row in the
disposable database has that status (`active` 3, `cancelled` 1).

This is the same stale-proxy fault recorded in the checkout follow-up above. It
recurred because the target had only been passed inline to a process, never
persisted. Fixed by adding a gitignored `frontend/.env` for the acceptance run
and by documenting `VITE_DEV_API_TARGET` in `frontend/.env.example`
(`3bbfa63`). No production code required a change; `manualOrderWorkflow.test.jsx`
already asserted `POST /api/v1/admin/orders/manual` and already passed.

After restarting only the 5175 process, the proxied POST answers 401 instead of
405 and the proxied OpenAPI matches the 8001 contract.

### Defect B — invoice filters returned 422

A real code defect, independent of Defect A. Reproduction B1 (`مستبدلة` +
`مدفوع جزئيًا`) failed even against the correct backend: the payment option
carried the value `partial`, while the API enum is `partially_paid`, so FastAPI
rejected the query and `main.py` returned the generic Arabic validation message.
Reproduction B2 (`مستبدلة` + all payment statuses) failed for Defect A's reason
instead — the 8000 backend does not know `replaced`.

Two further instances of the same drift were found by auditing the whole matrix:
an invoice stored as `partially_paid` rendered its raw English value, because the
label and badge-tone maps were also keyed on `partial`; and the payment-method
select offered `manual`, which the API rejects
(`cash_on_delivery|card|bank_transfer`). That value is posted by the manual-order
form, so choosing `تحويل يدوي / بنكي` failed a manager's save with the same 422.

Fixed in `eced41a`: `frontend/src/admin/orderInvoice/domain.js`,
`components.jsx`, `pages/InvoicesPages.jsx`. Regression tests assert submitted
values rather than Arabic labels: six tests were confirmed failing first, one of
them with `Value "partially_paid" not found in options` — Reproduction B1 as a
test.

No migration or backfill was needed: the disposable database holds no legacy
`issued` rows, and `InvoiceStatus.ISSUED` is an alias of `active` rather than a
stored value.

### Verification

`pytest` 367 passed, 4 pre-existing xfailed, 0 failed — no new xfails.
`npm.cmd test` 147 passed across 14 files. `npm.cmd run build` succeeded.
The running 5175 server serves the canonical values and proxies to 8001.

Disposable database: `backend/data/vista_browser_acceptance_20260804-154606.db`,
revision `0009_invoice_issuer_snapshot`; baseline before this work was orders 6,
order_items 40, invoices 4, order_activities 1, and no write was made to it.

### Browser acceptance limitation

Real-browser acceptance was **not** executed for either defect. This session had
no browser automation available and no manager password, so the scenarios could
not be driven or screenshotted. Defect A is evidenced at the transport layer
(405 → 401 through the proxy) and Defect B at the unit level; neither has
end-to-end browser evidence, and this document does not claim any.

`vista_preview.db` in the non-isolated checkout is held open by the port-8000
backend and its mtime moved during this session. Contact with 8000 was limited
to `GET /health`, `GET /openapi.json`, and one POST refused at routing before
any database access. The file is locked, so it could not be hashed to attest
byte-level equality.

### Out of scope, still open

`frontend/src/store.js` offers the public checkout a `manual` payment method,
which the API also rejects. It was left unchanged because it is public behaviour
outside both reported defects, and is recorded here as a known contract drift.
