# Order and Internal Invoice Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:using-git-worktrees` before implementation and `superpowers:verification-before-completion` before claiming completion.

**Goal:** Extend Vista Store's existing order/invoice implementation into a complete workflow where website orders are persisted before WhatsApp opens, staff can edit incomplete website orders, completing an order creates one immutable active internal invoice, managers can create manual orders and reopen completed orders, and payment changes are permission-controlled and fully auditable.

**Architecture:** Preserve and extend the existing `order` and `invoice` modules and migration history; do not create a parallel subsystem. The order remains the mutable operational record until completion. Completion runs in one database transaction, locks the order, snapshots its final values into an immutable invoice and invoice items, and records an audit event. Any post-completion correction must be performed by a manager through reopen/replace semantics, retaining the old invoice as cancelled or replaced.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, SQLite/MySQL-compatible schema, React, TypeScript, Vite, Vitest/Testing Library, existing admin authentication with `admin` and `super_admin` roles.

## Global Constraints

- Read and follow `docs/2026-08-03-order-invoice-workflow-design.md` as the authoritative product specification.
- Inspect the repository before editing; actual existing file names and module boundaries are the source of truth.
- Extend existing order/invoice models, services, routes, schemas, pages, and tests. Do not duplicate them under new competing modules.
- Preserve `backend/data/vista_preview.db` and `backend/data/vista_store_dev.db`; never delete, purge, reseed, overwrite, or commit them.
- Before applying a migration to any local non-test database, create timestamped `.bak` copies of both SQLite files.
- Do not run preview purge/seed commands.
- Do not modify catalog prices when an order line price changes.
- Manual order items must not create catalog products or change inventory.
- Preserve the project's existing inventory behavior for catalog items; do not invent new stock reservation or deduction behavior in this feature.
- All money values use the project's existing decimal/money representation. Never introduce binary floating-point calculations.
- Backend permission checks are authoritative. Hiding a frontend button is not authorization.
- Every material order, invoice, status, price, payment, refund, cancellation, reopen, or replacement change must create an immutable activity record.
- An order may have historical cancelled/replaced invoices, but at most one active invoice.
- A cancelled order never creates an invoice.
- Completing an order must be transactional and idempotent.
- The invoice is internal only: no customer PDF, invoice sharing, email, or automatic WhatsApp invoice delivery.
- No detailed multi-payment ledger is required. Store one primary payment method plus free-text payment details.
- Do not add dependencies unless the existing stack cannot implement a requirement.
- Use TDD and small commits. Do not leave placeholder handlers or mock-only production paths.
- Required verification:
  - Backend: `backend\.venv\Scripts\python.exe -m pytest -q`
  - Frontend: `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run lint`, `npm.cmd run build`
  - `git diff --check`
- Do not claim browser verification unless a real browser pass was performed and documented.

---

## Target Domain Model

Codex must first map these concepts onto the existing schema. Names below are the required semantic interfaces; adapt exact class/column names only where the repository already has an established equivalent.

### Enumerations

```python
class OrderSource(str, Enum):
    website = "website"
    whatsapp = "whatsapp"
    phone = "phone"
    walk_in = "walk_in"
    social = "social"
    other = "other"

class OrderStatus(str, Enum):
    new = "new"
    reviewing = "reviewing"
    preparing = "preparing"
    out_for_delivery = "out_for_delivery"
    completed = "completed"
    cancelled = "cancelled"

class OrderItemKind(str, Enum):
    catalog = "catalog"
    manual = "manual"

class InvoiceStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"
    replaced = "replaced"

class PaymentStatus(str, Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"
    partially_refunded = "partially_refunded"
    refunded = "refunded"

class PaymentMethod(str, Enum):
    cash_on_delivery = "cash_on_delivery"
    card = "card"
    bank_transfer = "bank_transfer"
```

### Required order snapshot semantics

Each order item must retain:

```python
product_id: int | None
kind: OrderItemKind
name_snapshot: str
sku_snapshot: str | None
description_snapshot: str | None
original_unit_price: Decimal
unit_price: Decimal
quantity: int
line_total: Decimal
```

A catalog product's current site price is never read back into an existing order except when staff explicitly adds that product as a new line. Updating `unit_price` affects only the order item.

### Required invoice snapshot semantics

Invoice and invoice items copy final order/customer/item/totals values at completion. Invoice reads must not depend on live product or mutable order values.

### Required activity event semantics

```python
order_id: int
invoice_id: int | None
actor_admin_id: int | None
event_type: str
before_data: dict | None
after_data: dict | None
reason: str | None
created_at: datetime
```

Use JSON columns where already supported by the project's SQLite/MySQL compatibility patterns; otherwise use canonical JSON text with serializer helpers and tests.

---

### Task 1: Repository inventory, safety baseline, and exact implementation map

**Files:**
- Read: `docs/2026-08-03-order-invoice-workflow-design.md`
- Read: `backend/alembic/versions/*`
- Read: existing backend order/invoice models, schemas, services, routers, dependencies, tests
- Read: existing frontend checkout, cart, order admin, invoice admin, routing, API, auth/role, modal/table components, and tests
- Create: `docs/superpowers/plans/2026-08-03-order-invoice-workflow-implementation.md` from this plan, corrected to exact repository paths
- Create: `docs/implementation/order-invoice-current-state.md`

**Interfaces:**
- Produces an exact file map, current endpoint map, current database fields, current status/payment behavior, current role dependency names, and a gap table against every design requirement.

- [ ] **Step 1: Create an isolated worktree**

Use the repository's current branch as the base and create a feature worktree/branch using `superpowers:using-git-worktrees`. Do not implement in the main working directory.

Suggested branch:

```text
feat/order-invoice-workflow
```

- [ ] **Step 2: Verify clean state**

Run from repository root:

```powershell
git status --short
git branch --show-current
git log -1 --oneline
```

Expected: no unexplained dirty files. The specification file may be uncommitted; if so, commit it separately before implementation.

- [ ] **Step 3: Inspect existing implementation**

Record exact paths and signatures for:

```text
Order model and item model
Invoice model and invoice item model
Existing order/invoice Alembic migration
Public order creation endpoint
Admin order endpoints
Invoice endpoints
Role dependencies
Audit logging
Checkout confirmation and WhatsApp builder
Admin order/invoice pages and services
Existing tests and fixture factories
```

- [ ] **Step 4: Inspect migration/database state without writes**

From `backend/`, using the test database or read-only inspection:

```powershell
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic history
```

Do not upgrade `vista_preview.db` or `vista_store_dev.db` during this task.

- [ ] **Step 5: Write the current-state document**

`docs/implementation/order-invoice-current-state.md` must include:

```markdown
# Current State
## Existing files
## Existing tables and columns
## Existing endpoints
## Existing frontend flow
## Existing permissions
## Existing tests
## Design gaps
## Exact files planned for each later task
## Data preservation risks
```

No `TBD` entries are allowed.

- [ ] **Step 6: Run baseline tests**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
cd ..
git diff --check
```

Record exact counts/results. Any pre-existing failure must be isolated and reported before feature edits.

- [ ] **Step 7: Commit documentation baseline**

```powershell
git add docs/2026-08-03-order-invoice-workflow-design.md docs/superpowers/plans/2026-08-03-order-invoice-workflow-implementation.md docs/implementation/order-invoice-current-state.md
git commit -m "docs: plan order and invoice workflow"
```

---

### Task 2: Database migration and backward-compatible domain fields

**Files:**
- Modify: exact existing backend order/invoice model files identified in Task 1
- Create: next Alembic migration after the current head, with a descriptive revision name
- Modify: model registration/import files required by Alembic
- Test: existing migration/model tests plus a new focused order/invoice schema test module

**Interfaces:**
- Produces persisted fields and constraints for order source/status/locking, order item snapshots, immutable invoice snapshots, payment state, replacement links, and activity logs.

- [ ] **Step 1: Write failing model/migration tests**

Tests must prove:

1. Existing orders/invoices can still be loaded after migration.
2. An order item stores `original_unit_price` separately from `unit_price`.
3. Manual items permit `product_id=None`.
4. Invoice items contain final snapshot fields.
5. Only one active invoice can exist per order at the service level; add a partial unique DB index only if it is portable across the project's supported databases.
6. Activity events persist old/new JSON and reason.
7. Replacement invoice links are retained.
8. New non-null fields have safe defaults/backfill behavior.

- [ ] **Step 2: Run focused tests and verify failure**

Use exact test paths discovered in Task 1:

```powershell
.\.venv\Scripts\python.exe -m pytest -q <focused-order-invoice-test-path>
```

Expected: failures for absent fields/tables.

- [ ] **Step 3: Implement the migration**

Migration rules:

- Alter existing tables rather than replacing them.
- Backfill existing orders as `source=website` unless existing data proves another safe mapping.
- Map existing statuses/payment values explicitly.
- Backfill item snapshots from existing order/invoice item values.
- Preserve IDs and relationships.
- Add indexes for:
  - order number
  - invoice number
  - order status/source/created date
  - invoice payment/status/created date
  - activity order/invoice/date
- Add foreign keys for completion actor, replacement invoice, activity actor where consistent with existing model conventions.
- Downgrade must remove only newly introduced schema and restore prior compatible values; it must not delete orders/invoices.

- [ ] **Step 4: Implement model enums and relationships**

Use existing timestamp, base, naming, and decimal conventions. Do not embed business transitions in model property setters.

- [ ] **Step 5: Run focused tests**

Expected: all migration/model tests pass on a fresh test DB.

- [ ] **Step 6: Test upgrade from the prior revision**

Create a disposable SQLite test DB at the previous revision, insert a representative legacy order/invoice fixture, upgrade to head, and assert the data is retained and readable.

- [ ] **Step 7: Commit**

```powershell
git add backend/app backend/alembic/versions backend/tests
git commit -m "feat(orders): extend order and invoice persistence"
```

---

### Task 3: Money calculations, payment derivation, and immutable activity service

**Files:**
- Create or modify: focused backend domain/service modules under the existing order/invoice package
- Test: focused unit tests for calculations, transitions, and audit recording

**Interfaces:**
- Produces:

```python
def calculate_order_totals(
    items: Sequence[OrderItemLike],
    discount_amount: Decimal,
    delivery_fee: Decimal,
) -> OrderTotals: ...

def derive_payment_status(
    total_amount: Decimal,
    paid_amount: Decimal,
    refunded_amount: Decimal,
) -> PaymentStatus: ...

def record_order_activity(
    db: Session,
    *,
    order_id: int,
    invoice_id: int | None,
    actor_admin_id: int | None,
    event_type: str,
    before_data: Mapping[str, Any] | None,
    after_data: Mapping[str, Any] | None,
    reason: str | None,
) -> OrderActivity: ...
```

- [ ] **Step 1: Write failing calculation tests**

Cover:

- quantity must be positive
- unit prices, discount, delivery fee, paid, and refunded values cannot be negative
- subtotal is sum of quantized line totals
- total cannot become negative
- `remaining_amount = total - net_paid`, bounded at zero
- unpaid/partial/paid derivation
- partial/full refund derivation
- employee payment cannot decrease paid amount
- manager correction/refund requires a non-empty reason

- [ ] **Step 2: Implement pure calculation functions**

All money inputs and outputs use `Decimal` and the project's configured currency scale/rounding.

- [ ] **Step 3: Write failing activity tests**

Assert an event is recorded for:

- product add/remove
- quantity change
- price change
- discount/delivery change
- customer detail change
- status change
- completion
- payment update
- refund/correction
- reopen
- invoice replacement

- [ ] **Step 4: Implement activity serializer**

Serialize only stable business fields; never serialize SQLAlchemy internals, secrets, JWTs, or complete admin objects.

- [ ] **Step 5: Run tests and commit**

```powershell
git add backend/app backend/tests
git commit -m "feat(orders): add totals and activity domain services"
```

---

### Task 4: Public checkout creates the order before WhatsApp

**Files:**
- Modify: existing public order schema/service/router
- Modify: frontend checkout/order API service and checkout confirmation page/component
- Test: backend public order tests and frontend checkout/WhatsApp tests

**Interfaces:**
- Public request must include a client-generated idempotency reference.
- Public response must include the canonical order number and server-calculated final snapshot needed to build the WhatsApp message.

Suggested semantic contract:

```json
POST /api/v1/orders
{
  "client_reference": "uuid",
  "customer": {
    "name": "...",
    "phone": "...",
    "address": "..."
  },
  "delivery_area_id": 1,
  "notes": "...",
  "items": [
    {"product_id": 123, "quantity": 2}
  ]
}
```

```json
{
  "id": 42,
  "order_number": "ORD-20260803-0042",
  "status": "new",
  "source": "website",
  "customer_name": "...",
  "customer_phone": "...",
  "customer_address": "...",
  "notes": "...",
  "items": [
    {
      "name": "...",
      "sku": "...",
      "quantity": 2,
      "unit_price": "25.00",
      "line_total": "50.00"
    }
  ],
  "subtotal": "50.00",
  "discount_amount": "0.00",
  "delivery_fee": "5.00",
  "total_amount": "55.00"
}
```

- [ ] **Step 1: Write failing backend tests**

Prove:

- order persists before any WhatsApp behavior
- server reads current catalog names/SKU/prices and snapshots them
- inactive/missing products and invalid quantities are rejected
- totals are server-calculated
- source/status are `website`/`new`
- duplicate `client_reference` returns the same created order, not a duplicate
- creation failure leaves no partial order/items

- [ ] **Step 2: Implement public order creation transaction**

Do not trust client price/name/totals.

- [ ] **Step 3: Write failing frontend tests**

Prove:

- clicking confirmation calls create-order first
- WhatsApp is not opened when API creation fails
- message uses returned order number and returned server snapshot
- double click does not create duplicate calls while pending
- cart clears only after successful order creation
- Arabic message contains customer details, items, totals, delivery, notes when supplied

- [ ] **Step 4: Implement frontend flow**

Use the existing store WhatsApp number/settings source. Navigate/open WhatsApp only after API success. Avoid popup-blocker regressions by following a tested browser-safe pattern already used in the project.

- [ ] **Step 5: Run tests and commit**

```powershell
git add backend/app backend/tests frontend/src
git commit -m "feat(checkout): persist orders before WhatsApp"
```

---

### Task 5: Admin order read/edit API with role-safe state transitions

**Files:**
- Modify: existing admin order router/schema/service
- Modify: shared admin role dependency only if necessary
- Test: backend admin order API/service tests

**Interfaces:**

```text
GET    /api/v1/admin/orders
GET    /api/v1/admin/orders/{order_id}
PATCH  /api/v1/admin/orders/{order_id}
```

Use repository naming conventions if current endpoints differ.

The edit endpoint should accept one complete editable order draft plus a required `reason` when material values change. The backend computes the diff and activity events; the client must not submit its own audit log.

- [ ] **Step 1: Write failing list/detail tests**

Filters:

- search by order number, customer name, phone
- status
- source
- payment status
- date range
- pagination/sort using existing conventions

Detail includes:

- original item snapshot values
- current item values
- totals
- customer/delivery/notes
- status/source
- active/historical invoice references
- ordered activity timeline

- [ ] **Step 2: Write failing edit tests**

Both `admin` and `super_admin` may edit an incomplete website order:

- add catalog item
- remove item
- change quantity
- increase/decrease unit price
- change discount/delivery fee
- change customer fields
- add internal notes
- transition among allowed incomplete statuses
- cancel an incomplete order

Reject:

- empty order
- manual item added by normal admin
- editing completed/cancelled locked order
- completing through generic PATCH
- invalid transition
- catalog price mutation
- missing reason for material edit
- stale concurrent edit if the project has version/update timestamps; use optimistic protection consistent with existing architecture

- [ ] **Step 3: Implement transactional edit service**

Lock/read the order, validate permissions/state, replace/update lines safely, calculate totals, create granular activity records, and commit once.

- [ ] **Step 4: Run tests and commit**

```powershell
git add backend/app backend/tests
git commit -m "feat(admin): edit incomplete website orders"
```

---

### Task 6: Transactional completion and immutable active invoice creation

**Files:**
- Modify: order/invoice service, schema, router
- Test: completion/concurrency/invoice snapshot tests

**Interfaces:**

```text
POST /api/v1/admin/orders/{order_id}/complete
```

Payload:

```json
{
  "payment_method": "cash_on_delivery",
  "paid_amount": "0.00",
  "payment_details": "",
  "invoice_notes": ""
}
```

Payment status and remaining amount are server-derived.

- [ ] **Step 1: Write failing completion tests**

Prove:

- both roles can complete an eligible order
- no-item order is rejected
- cancelled/completed order is rejected
- invoice is created only by completion
- order status becomes completed and is locked
- invoice and invoice items are snapshots
- invoice shows final unit price only
- completion actor/time are stored
- one active invoice exists
- duplicate/retried completion is idempotent and does not create a second invoice
- transaction rollback leaves neither completed order nor partial invoice
- catalog prices changing after completion do not change invoice values

- [ ] **Step 2: Implement one completion transaction**

Within one transaction:

1. lock/load order
2. validate state/items/totals/payment
3. set completed fields
4. create invoice
5. copy customer/order/item/totals fields
6. create invoice items
7. record completion activity
8. flush and return canonical detail

- [ ] **Step 3: Add final-review response/schema support**

The frontend can calculate previews, but the completion dialog must display values fetched from the latest order detail immediately before confirmation.

- [ ] **Step 4: Run tests and commit**

```powershell
git add backend/app backend/tests
git commit -m "feat(invoices): create immutable invoice on completion"
```

---

### Task 7: Invoice listing and permission-controlled payment updates

**Files:**
- Modify: existing invoice admin router/schema/service
- Test: invoice filter and payment permission tests

**Interfaces:**

```text
GET   /api/v1/admin/invoices
GET   /api/v1/admin/invoices/{invoice_id}
PATCH /api/v1/admin/invoices/{invoice_id}/payment
POST  /api/v1/admin/invoices/{invoice_id}/refund
```

Adapt endpoint names to existing conventions.

- [ ] **Step 1: Write failing invoice read tests**

Filters:

- invoice number
- order number
- customer
- source
- invoice status
- payment status
- employee/completer
- date range

Detail includes replacement links and activity history.

- [ ] **Step 2: Write failing normal-admin payment tests**

Normal admin may:

- increase `paid_amount` up to invoice total
- select primary method
- update payment details
- progress unpaid → partial → paid

Normal admin may not:

- reduce paid amount
- set refund statuses
- record refunded amount
- change an active invoice to cancelled/replaced
- modify snapshot/customer/items/totals
- revert fully paid to unpaid/partial

- [ ] **Step 3: Write failing manager payment/correction tests**

Manager may, with mandatory reason:

- reduce/correct paid amount
- record partial/full refund
- change method/details for correction
- derive partial/full-refund status

Reject paid/refunded amounts outside valid bounds.

- [ ] **Step 4: Implement payment service**

Store paid/refunded/remaining fields, derive status, and create activity events. Do not build a multi-payment table.

- [ ] **Step 5: Run tests and commit**

```powershell
git add backend/app backend/tests
git commit -m "feat(invoices): manage internal payment status"
```

---

### Task 8: Manager-only manual orders and manual line items

**Files:**
- Modify: order schemas/services/routes
- Test: role and manual-order tests

**Interfaces:**

```text
POST /api/v1/admin/orders/manual
```

Supports saving an incomplete manual order or atomically creating-and-completing it when completion data is included.

Semantic item union:

```python
class CatalogOrderItemInput(BaseModel):
    kind: Literal["catalog"]
    product_id: int
    quantity: int
    unit_price: Decimal | None = None

class ManualOrderItemInput(BaseModel):
    kind: Literal["manual"]
    name: str
    description: str | None = None
    quantity: int
    unit_price: Decimal
```

- [ ] **Step 1: Write failing authorization tests**

- normal admin receives 403
- manager/super_admin can create
- source cannot be `website` for manual endpoint
- `other` source requires a source note/label if the design/current project supports it

- [ ] **Step 2: Write failing item behavior tests**

- catalog item snapshots catalog identity and default price
- manager may override order-line price
- manual item has no product relation
- manual item does not create/update product or inventory rows
- mixed catalog/manual items calculate correctly
- empty order rejected
- incomplete save creates no invoice
- complete option creates exactly one active invoice transactionally

- [ ] **Step 3: Implement and commit**

```powershell
git add backend/app backend/tests
git commit -m "feat(orders): add manager manual order entry"
```

---

### Task 9: Manager-only reopen and invoice replacement workflow

**Files:**
- Modify: order/invoice services/routes/schemas
- Test: reopen/replacement/audit tests

**Interfaces:**

```text
POST /api/v1/admin/orders/{order_id}/reopen
```

Payload:

```json
{"reason": "Customer correction after completion"}
```

- [ ] **Step 1: Write failing authorization/state tests**

- normal admin gets 403
- manager must provide reason
- only completed order with active invoice may reopen
- already reopened/incomplete/cancelled order is rejected
- old invoice is never deleted

- [ ] **Step 2: Write failing replacement tests**

After reopen:

- old active invoice becomes `replaced` or `cancelled` according to the project's chosen distinction
- order unlocks for manager editing
- normal admin still cannot edit this manager-reopened order unless the approved spec explicitly allows it; use manager-only editing until recompletion
- recompletion creates a new invoice number
- new invoice points to prior invoice and prior points to replacement
- exactly one active invoice remains
- activity records actor, reason, old invoice, new invoice, timestamps

- [ ] **Step 3: Implement transaction and commit**

```powershell
git add backend/app backend/tests
git commit -m "feat(invoices): reopen orders and replace invoices"
```

---

### Task 10: Frontend API contracts, types, role capabilities, and shared editors

**Files:**
- Modify/create: frontend API modules for orders/invoices
- Modify: shared domain types
- Create/modify: reusable order line editor, totals summary, status/payment badges, activity timeline, completion dialog
- Test: API mapping and component tests

**Interfaces:**

Create one canonical frontend domain representation matching backend responses. Avoid duplicated incompatible `Order`/`Invoice` types in page files.

Required reusable components:

```tsx
<OrderItemsEditor />
<OrderTotalsSummary />
<OrderStatusBadge />
<PaymentStatusBadge />
<OrderActivityTimeline />
<CompleteOrderDialog />
```

- [ ] **Step 1: Write failing API/type tests**

Validate decimal strings remain strings or are converted only through the project's existing money utility, never plain floating-point arithmetic.

- [ ] **Step 2: Implement API modules and capability helpers**

Capabilities are UI hints only:

```ts
canCreateManualOrder(role)
canReopenOrder(role)
canCorrectPayment(role)
canUpdateRoutinePayment(role)
```

Backend remains authoritative.

- [ ] **Step 3: Write and implement component tests**

Cover accessible labels, RTL, mobile layout, keyboard operation, loading/error states, and disabled states.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src
git commit -m "feat(admin): add order and invoice UI foundations"
```

---

### Task 11: Admin orders list, detail editor, and completion workflow

**Files:**
- Modify: existing admin orders page/routes/navigation
- Create/modify: order detail workspace/editor components
- Test: page integration tests

**Required UX:**

Orders list:

- search order number/name/phone
- filters status/source/date/payment
- display order number, customer, source, status, payment, total, created date
- WhatsApp action
- open detail

Order detail:

- customer/source/original and current items
- editable catalog lines for incomplete website orders
- quantity and price increase/decrease
- add/remove catalog product
- discount/delivery
- internal notes and required edit reason
- activity timeline
- status transitions
- completion review dialog

- [ ] **Step 1: Write failing list tests**
- [ ] **Step 2: Implement list with URL-backed filters if existing admin pages use that convention**
- [ ] **Step 3: Write failing edit tests**
- [ ] **Step 4: Implement editor and server error handling**
- [ ] **Step 5: Write failing completion tests**
- [ ] **Step 6: Implement latest-data review and completion**
- [ ] **Step 7: Verify normal admin cannot see manager-only controls**
- [ ] **Step 8: Commit**

```powershell
git add frontend/src
git commit -m "feat(admin): manage and complete orders"
```

---

### Task 12: Admin invoices page and payment workflow

**Files:**
- Modify/create: invoice route/page/components/navigation
- Test: list/detail/payment permission integration tests

**Required UX:**

- search invoice/order/customer
- filters date/payment/source/employee/invoice status
- active/cancelled/replaced visual distinction
- detail shows final prices only
- payment method, paid, remaining, details
- normal update flow
- manager correction/refund flow with reason
- replacement links
- no customer-facing print/share/PDF control

- [ ] **Step 1: Write failing invoice page tests**
- [ ] **Step 2: Implement list/detail**
- [ ] **Step 3: Write failing role/payment tests**
- [ ] **Step 4: Implement routine vs manager-sensitive forms**
- [ ] **Step 5: Commit**

```powershell
git add frontend/src
git commit -m "feat(admin): archive invoices and update payments"
```

---

### Task 13: Manager manual-order page and reopen UI

**Files:**
- Modify: admin navigation/routes
- Create: manager manual-order workspace
- Modify: order/invoice detail manager controls
- Test: role and workflow integration tests

**Required UX:**

Manual order:

- manager-only route and server guard
- source selector: WhatsApp, phone, walk-in, social, other
- customer fields
- catalog item search/add
- manual item add with name, optional description, quantity, unit price
- discount/delivery/payment/details/notes
- save incomplete or complete and invoice

Reopen:

- manager-only action
- mandatory reason confirmation
- clear warning that old invoice remains archived
- after replacement, links between old/new invoices

- [ ] **Step 1: Write failing route/role tests**
- [ ] **Step 2: Implement manual-order workspace**
- [ ] **Step 3: Write failing reopen UI tests**
- [ ] **Step 4: Implement reopen/replacement navigation**
- [ ] **Step 5: Commit**

```powershell
git add frontend/src
git commit -m "feat(admin): add manual orders and invoice replacement UI"
```

---

### Task 14: Migration safety, full regression, browser acceptance, and documentation

**Files:**
- Modify: relevant README/admin workflow docs
- Create: `docs/implementation/order-invoice-acceptance.md`
- Test: full backend/frontend suites

- [ ] **Step 1: Back up local SQLite files before any non-test migration**

From repo root, choose a timestamp:

```powershell
Copy-Item backend\data\vista_preview.db backend\data\vista_preview.db.<timestamp>.bak
Copy-Item backend\data\vista_store_dev.db backend\data\vista_store_dev.db.<timestamp>.bak
```

Verify both backups exist and are non-zero. Never stage them.

- [ ] **Step 2: Run migration on a disposable copy first**

Copy the preview DB to a temporary QA DB, point `DATABASE_URL` to it, run upgrade head, and execute focused smoke queries/tests. Do not migrate the original until the disposable-copy result passes.

- [ ] **Step 3: Full backend verification**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] **Step 4: Full frontend verification**

```powershell
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

- [ ] **Step 5: Static verification**

```powershell
cd ..
git diff --check
git status --short
```

- [ ] **Step 6: Real browser acceptance**

Run the app against the intended preview DB and verify at minimum desktop and mobile:

1. website order is saved before WhatsApp
2. WhatsApp message includes canonical order number and returned totals
3. admin sees new order
4. normal admin edits quantity and order-only price without catalog change
5. normal admin completes and invoice appears
6. normal admin increases paid amount
7. normal admin cannot reduce payment/reopen/manual order
8. manager creates manual order with manual item
9. manager reopens completed order and replaces invoice
10. old invoice remains visible as replaced
11. searches and filters work
12. invoice has no customer sharing/PDF controls

Record widths, browser, results, and any limitations.

- [ ] **Step 7: Write acceptance report**

`docs/implementation/order-invoice-acceptance.md` must include:

- exact migration revision
- exact files changed
- exact API endpoints
- permission matrix
- test command outputs/counts
- browser test evidence
- database backup paths
- proof catalog prices remain unchanged
- proof manual items do not affect catalog/inventory
- proof one active invoice per completed order
- known limitations matching the design's out-of-scope section

- [ ] **Step 8: Final commit**

```powershell
git add backend frontend docs
git commit -m "feat: complete order and internal invoice workflow"
```

- [ ] **Step 9: Verification-before-completion**

Invoke `superpowers:verification-before-completion`. Re-run the decisive commands and report evidence, not assumptions.

---

## Required backend acceptance matrix

| Scenario | Expected |
|---|---|
| Public order creation fails | No WhatsApp navigation; no partial DB rows |
| Public order request repeats with same client reference | Same order returned; no duplicate |
| Staff edits line price | Order line changes; catalog price unchanged |
| Staff completes valid order | Order locks; one active invoice created |
| Staff retries completion | No duplicate invoice |
| Staff tries manual order | 403 |
| Manager creates manual item | Item remains order/invoice-only |
| Staff increases payment | Allowed and audited |
| Staff reduces payment | Rejected |
| Manager corrects/refunds with reason | Allowed and audited |
| Staff reopens completed order | 403 |
| Manager reopens | Old invoice retained and replaced/cancelled |
| Recompleted order | New active invoice; old invoice linked |
| Cancelled order | No invoice |
| Invoice read after catalog edit | Invoice snapshot unchanged |

## Required frontend acceptance matrix

| Surface | Required |
|---|---|
| Checkout | Create order first; then WhatsApp |
| Orders list | Search/filter/status/source/payment/date |
| Order detail | Edit incomplete website order; activity timeline |
| Completion dialog | Latest final items/totals/payment review |
| Invoices | Internal archive, final prices only |
| Payment UI | Routine staff updates; manager corrections |
| Manual orders | Manager only; catalog + manual items |
| Reopen | Manager-only reason dialog and replacement links |
| Mobile | No clipped tables/forms; usable dialogs/drawers |
| Accessibility | Labels, focus, keyboard operation, status text |

## Explicit non-goals

Do not implement:

- customer invoice delivery
- invoice PDF
- customer invoice portal
- tax/legal accounting
- external accounting integration
- online payment gateway
- detailed split-payment ledger
- automatic customer order-status notifications
- new inventory reservation system
- catalog creation from manual items
