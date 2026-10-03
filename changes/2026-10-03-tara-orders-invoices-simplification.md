# Tara Orders and Invoices Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the restrictive order/invoice workflow with four order states, invoice-at-completion, editable completed orders/current invoices, simple payment states, delta-based inventory adjustment, and an explicit Admin negative-stock override.

**Architecture:** Preserve historical rows and audit data while simplifying the active workflow. Current orders use four canonical statuses. Invoices are created only when an order enters `completed`; while the order remains completed the same active invoice is synchronized in place. Leaving `completed` archives/cancels that invoice, and re-completing creates a new numbered invoice. Inventory remains server-authoritative and public checkout remains strict; only an explicit authenticated Admin correction may allow negative stock.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React Admin UI, Vitest, Pytest, SQLite, MySQL 8.

**Spec:** `docs/superpowers/specs/2026-10-03-tara-customer-change-batch-design.md`

## Global Constraints

- Canonical active order statuses: `new`, `ready`, `completed`, `cancelled`.
- Migrate current `confirmed` → `ready` and current `delivered` → `completed`.
- Keep historical/legacy status strings readable where necessary; do not rewrite historical activity/status-history rows without a specific need.
- Invoices are issued only when entering `completed`.
- Completed orders remain editable after a strong confirmation warning.
- While the order stays `completed`, update the same active invoice row and keep the same invoice number.
- Leaving completed archives/cancels the active invoice; re-entering completed creates a new invoice number.
- Payment UI states only: `unpaid`, `paid`, `refunded`; correction reason is optional.
- If total changes: paid stays paid at new total; refunded stays fully refunded at new total; unpaid remains zero paid with remaining=new total.
- Admin inventory edits use quantity delta and may go negative only after explicit warning/override.
- Public checkout continues rejecting insufficient tracked stock and has no override flag.
- Meaningful completed-order and invoice mutations are written to the append-only activity log.
- No GitHub push and no Production deployment in this plan.

## Review Focus

- `completed → ready → completed` must not double-consume or restore stock; Tasks 2 and 4 add lifecycle tests.
- Editing a completed line from one variant to another must restore old variant stock and consume new variant stock exactly once; Task 4 tests it.
- Negative-stock override must be impossible through public checkout and impossible through Admin unless the explicit confirmation flag is present; Task 4 tests both paths.
- Paid/refunded/unpaid invoices must never keep stale money fields after total changes; Task 3 tests state normalization.
- Migration must normalize current order status without changing invoice numbers or rewriting historical status/activity records; Task 1 tests migration behavior.

---

## File Map

### Backend

- Modify: `backend/app/core/enums.py` — keep legacy read compatibility while defining/using the canonical mutable statuses.
- Modify: `backend/app/models/catalog.py` — remove product/variant non-negative stock DB constraints from ORM metadata.
- Modify: `backend/app/models/orders.py` — support simplified active workflow; keep compatibility columns such as `is_locked` if physical removal is unnecessary.
- Modify: `backend/app/models/invoices.py` — current active invoice becomes a mutable operational snapshot; archived rows remain history.
- Modify: `backend/app/schemas/orders.py` — canonical status/update payloads and explicit Admin negative-stock confirmation field.
- Modify: `backend/app/schemas/invoices.py` — state-based payment update payload.
- Modify: `backend/app/services/orders.py` — canonical transitions, completed edits, stock deltas, invoice hooks.
- Modify: `backend/app/services/invoices.py` — issue, archive, synchronize active invoice, state-based payment normalization.
- Modify: `backend/app/api/v1/endpoints/admin_commerce.py` — Admin order edit/status interface.
- Modify: `backend/app/api/v1/endpoints/admin_invoices.py` — simplified payment endpoint.
- Create: next Alembic migration(s) from the actual current head — status normalization and safe removal of stock non-negative checks on SQLite/MySQL.
- Test: `backend/tests/test_admin_order_edit.py`, `backend/tests/test_invoices.py`, `backend/tests/test_order_invoice_domain.py`, `backend/tests/test_order_invoice_persistence.py`, `backend/tests/test_migrations.py`, `backend/tests/test_checkout.py`.

### Frontend

- Modify: `frontend/src/admin/orderInvoice/domain.js` — canonical four status choices and three payment choices; remove lock/super-admin-only UI gates that contradict the approved workflow.
- Modify: `frontend/src/admin/pages/OrdersPages.jsx` — completed-order warning, simplified status controls, negative-stock confirmation flow, packaging edit support.
- Modify: `frontend/src/admin/pages/InvoicesPages.jsx` — direct payment-state control and optional reason.
- Modify: `frontend/src/admin/orderInvoice/components.jsx` as needed for shared warning/activity display.
- Modify: `frontend/src/api/adminApi.js` — changed Admin payloads.
- Test: existing Admin/order/invoice tests; add focused regression test files if current files are too broad.

---

### Task 1: Canonical Four-State Order Lifecycle and Data Migration

**Interfaces:**
- Produces: normal mutable status allowlist `{new, ready, completed, cancelled}`.
- Legacy enum strings may remain readable but are never offered as normal new transitions.

- [ ] **Step 1: Write failing backend migration/domain tests**
  - Existing current order `confirmed` becomes `ready`.
  - Existing current order `delivered` becomes `completed`.
  - Existing `order_status_history` rows retain their original values.
  - Normal mutation endpoint rejects `confirmed`, `delivered`, and other legacy aliases as new target states.
  - No invoice is issued for `new` or `ready`.

- [ ] **Step 2: Run focused tests and verify failure**
  - Run: `cd backend && pytest tests/test_order_invoice_domain.py tests/test_migrations.py -q`
  - Expected: new canonical-lifecycle assertions fail.

- [ ] **Step 3: Implement canonical status validation**
  - Preserve legacy read labels/compatibility only where old rows need them.
  - Replace transition tables and service logic that expose `confirmed` or `delivered` as current workflow targets.
  - Enforce this in the backend, not only in the React UI.

- [ ] **Step 4: Add the migration**
  - Generate from the current Alembic head.
  - Update only current `orders.status` values for the two approved mappings.
  - If legacy `is_locked` state would still block the approved workflow, neutralize it safely in migration/service behavior while retaining the column unless physical removal is clearly required.
  - Do not rewrite historical `order_status_history` or `order_activities` rows.

- [ ] **Step 5: Update Admin status choices and edit eligibility**
  - `ORDER_STATUSES` exposes only new/ready/completed/cancelled.
  - Remove old `is_locked`/completed-status gates from normal edit eligibility where they conflict with the new design.
  - Preserve authentication and Admin-role boundaries unrelated to the removed workflow restrictions.

- [ ] **Step 6: Run focused backend and frontend tests**
  - Expected: PASS.

- [ ] **Step 7: Commit locally**
  - `git commit -m "feat: simplify order lifecycle"`

---

### Task 2: Invoice Only on Completion and Active-Invoice Synchronization

**Interfaces:**
- Keep issue/archive/sync responsibilities separate in `services/invoices.py`.
- Recommended service boundaries (exact names may follow current conventions):
  - `issue_for_order(...) -> Invoice`
  - `archive_active_for_order(..., reason: str | None) -> Invoice | None`
  - `sync_active_from_order(..., admin: AdminUser, reason: str | None = None) -> Invoice`

- [ ] **Step 1: Write failing lifecycle/persistence tests**
  - New→ready: no invoice.
  - Ready→completed: one active invoice is issued.
  - Editing an order while it remains completed: same invoice ID and number, updated customer/items/totals/packaging snapshot.
  - Completed→ready or new: active invoice is archived/cancelled, historical row retained, stock remains held.
  - Ready/new→completed again: a new invoice number is issued and the old invoice remains historical.
  - Completed→cancelled: stock is restored exactly once and active invoice is archived/cancelled.
  - Completed→ready→completed does not consume or restore stock merely because of invoice lifecycle transitions.

- [ ] **Step 2: Run focused tests and verify failure**
  - Run: `cd backend && pytest tests/test_invoices.py tests/test_order_invoice_persistence.py -q`

- [ ] **Step 3: Move invoice issuance trigger to `completed`**
  - Remove issue-on-confirmed behavior.
  - Make repeated calls/transitions idempotent for the same active state.

- [ ] **Step 4: Implement current active invoice synchronization**
  - Recopy current order customer/delivery/packaging/money snapshot.
  - Replace active invoice item snapshots to match the edited completed order.
  - Keep invoice number and original `issued_at` when merely editing while still completed.
  - Record stable before/after activity data.

- [ ] **Step 5: Implement archive semantics when leaving completed**
  - Reuse existing `cancelled`/`replaced` semantics consistently with the current active-marker uniqueness model.
  - Never delete invoice rows and never reuse invoice numbers.

- [ ] **Step 6: Run focused tests, then full backend suite**
  - Expected: PASS except existing documented xfails.

- [ ] **Step 7: Commit locally**
  - `git commit -m "feat: simplify completed invoice lifecycle"`

---

### Task 3: Three-State Payment Editing

**Interfaces:**
- Admin update supplies `payment_status` in `{unpaid, paid, refunded}` plus optional `reason`.
- Backend derives `paid_amount`, `refunded_amount`, and `remaining_amount` from current invoice total.

- [ ] **Step 1: Write failing backend payment tests**
  - For total `T`, `unpaid` ⇒ paid 0, refunded 0, remaining T.
  - `paid` ⇒ paid T, refunded 0, remaining 0.
  - `refunded` ⇒ paid T, refunded T, remaining 0.
  - Reason is optional for every transition.
  - An authorized regular Admin may use all three states; super-admin is not required solely for these transitions.
  - Historical partial states remain readable but new updates never emit partial states.
  - After total changes, a paid/refunded/unpaid invoice is normalized to the same rules using the new `T`.

- [ ] **Step 2: Run invoice tests and verify failure**

- [ ] **Step 3: Replace amount-driven update with state-driven backend API/service**
  - Do not trust client-provided paid/refunded monetary fields in the new flow.
  - Keep compatibility helpers only if existing historical-read code still needs them.
  - Write optional reason to activity log when provided.

- [ ] **Step 4: Update Admin invoice UI**
  - Primary control becomes direct selector: غير مدفوع / مدفوع / مردود.
  - Reason field remains optional.
  - Remove normal-user workflow for manually entering paid/refunded amounts and mandatory correction reason.

- [ ] **Step 5: Run frontend and backend tests**

- [ ] **Step 6: Commit locally**
  - `git commit -m "feat: simplify invoice payment status"`

---

### Task 4: Completed-Order Editing, Inventory Deltas, and Negative-Stock Override

**Interfaces:**
- Admin edit API includes an explicit confirmation boolean such as `allow_negative_stock` only on authenticated Admin edits.
- Public checkout never accepts or honors that flag.
- Inventory-delta logic compares the old committed catalog lines with the proposed new lines and applies only the difference.

- [ ] **Step 1: Write failing inventory/edit tests**
  - Completed quantity 2→3 consumes 1 additional unit.
  - 3→1 returns 2.
  - Removing a line returns its committed quantity.
  - Adding a line consumes its quantity.
  - Switching product/variant restores old commitment and consumes the new one.
  - Untracked products remain unaffected by stock deltas.
  - If stock would go negative and override is false, backend returns a structured conflict/warning with enough product/variant detail for UI confirmation.
  - The same Admin edit succeeds with `allow_negative_stock=true` and persists negative tracked stock.
  - Public checkout with insufficient tracked stock still fails and cannot provide the Admin override.
  - Successful completed edit synchronizes the active invoice after order totals/items are finalized.

- [ ] **Step 2: Run focused tests and verify failure**
  - Run: `cd backend && pytest tests/test_admin_order_edit.py tests/test_checkout.py tests/test_order_invoice_persistence.py -q`

- [ ] **Step 3: Remove database non-negative stock constraints**
  - Remove `ck_products_stock_non_negative` and `ck_variants_stock_non_negative` from ORM metadata.
  - Add Alembic migration using SQLite batch operations and MySQL-safe constraint drops.
  - Preserve order/invoice quantity-positive constraints.

- [ ] **Step 4: Implement inventory-delta calculation**
  - Do not reuse blanket `max(0, ...)` behavior in the Admin override path.
  - Keep normal public order creation stock validation unchanged.
  - Apply changes transactionally with order edit + invoice sync + activity write.

- [ ] **Step 5: Add the completed-order warning in Admin UI**
  - Before editing/saving a completed order, require explicit confirmation using the approved warning meaning:
    `هذا الطلب مكتمل وتم تسجيل بياناته وفاتورته في النظام. أي تعديل من الآن قد يغيّر البيانات المالية أو المخزون. تأكد من التعديلات قبل الحفظ، وأنت مسؤول عن صحة البيانات الجديدة.`
  - Buttons: cancel / continue.

- [ ] **Step 6: Add negative-stock confirmation flow**
  - First submit without override.
  - If backend reports that the change would make stock negative, show the approved warning:
    `الكمية المطلوبة أكبر من المخزون المتوفر حاليًا، واستمرار التعديل سيجعل المخزون بالسالب. هل تريد المتابعة؟`
  - Cancel stops. Continue resubmits once with explicit Admin override.

- [ ] **Step 7: Make completed orders fully editable per approved scope**
  - Remove obsolete UI locks that prevent customer/address/items/prices/discount/delivery/packaging edits after completion.
  - Keep unrelated auth/role protections.
  - Recalculate packaging and totals server-side.

- [ ] **Step 8: Run focused tests, full suites, and migration gates**
  - Include MySQL 8 migration/test gate.

- [ ] **Step 9: Commit locally**
  - `git commit -m "feat: allow audited completed order corrections"`

---

### Task 5: Batch B Verification

- [ ] Run all focused order/invoice/backend tests and then `cd backend && pytest -q`.
- [ ] Run `cd frontend && npm test` and `cd frontend && npm run build`.
- [ ] Run Alembic upgrade smoke on disposable SQLite and the repository's MySQL 8 gate.
- [ ] Run `git diff --check`.
- [ ] Manually smoke locally: `new → ready → completed → edit paid invoice total → ready → completed → cancelled`.
- [ ] During smoke, record exact stock before/after and invoice IDs/numbers to prove no double stock movement and correct invoice history.
- [ ] Verify exact stock quantities are still hidden from normal storefront browsing and public checkout still rejects insufficient tracked stock.
- [ ] Summarize migrations, changed business rules, and compatibility paths retained.
- [ ] **STOP. Do not push and do not deploy.**
