You are working in this repository:

D:\Project\vista-store-e-commerce

Act as the senior engineer responsible for fully implementing the approved order and internal invoice workflow. This is an implementation task, not another brainstorming or design-only task.

## Required skills and workflow

Use the installed Superpowers workflow:

1. Read and follow `superpowers:using-superpowers`.
2. Use `superpowers:using-git-worktrees` before implementation.
3. Use `superpowers:writing-plans` only to validate/correct the existing implementation plan against the real repository.
4. Execute with `superpowers:subagent-driven-development` (preferred) or `superpowers:executing-plans`.
5. Use TDD for every task.
6. Use `superpowers:requesting-code-review` at meaningful milestones.
7. Use `superpowers:verification-before-completion` before claiming success.

Do not ask me to restate requirements already present in the documents. Make reasonable implementation decisions that preserve the approved design and existing project patterns. Stop and report only if a genuine external blocker makes implementation impossible.

## Authoritative documents

Read these completely before touching production code:

- `docs/2026-08-03-order-invoice-workflow-design.md`
- `docs/superpowers/plans/2026-08-03-order-invoice-workflow-implementation-plan.md`

The design document defines product behavior. The implementation plan defines the required task sequence, tests, safety constraints, and acceptance criteria.

## First required action: repository inspection

Before changing code:

1. Inspect Git status, current branch, HEAD, remotes, and existing worktrees.
2. Locate the existing order and invoice implementation:
   - SQLAlchemy models
   - Alembic migration `0003_invoices` and every later migration
   - schemas
   - services
   - public/admin routers
   - authentication and `admin` / `super_admin` permission dependencies
   - audit logging
   - backend tests
   - checkout/cart WhatsApp flow
   - frontend order/invoice APIs, types, pages, routes, navigation, components, and tests
3. Confirm the actual current Alembic head and current database configuration.
4. Update the implementation plan's file paths and interface names to match the repository exactly. Do not change the approved behavior.
5. Write `docs/implementation/order-invoice-current-state.md` with the exact existing implementation and design gaps.
6. Run the complete baseline test suite before feature changes.

Do not build a second parallel order/invoice subsystem. Extend and refactor the existing one.

## Critical data-safety rules

The repository has local SQLite database files under `backend\data`, including:

- `backend\data\vista_preview.db`
- `backend\data\vista_store_dev.db`

Treat both as valuable untracked local data:

- Never delete, purge, reset, overwrite, reseed, or commit either database.
- Never run preview purge/seed commands.
- Re-check their actual Alembic revisions; do not rely blindly on an old report.
- Before applying any migration to either original file, make timestamped non-zero `.bak` copies of both.
- Test the migration first against a disposable copied database.
- Do not touch production/cPanel/R2 resources.
- Do not expose secrets in output or commits.
- Ensure no `.db`, `.bak`, `.env`, credentials, or generated media become staged.

## Required product behavior

Implement the complete approved workflow:

### Website checkout

- Persist the order in the backend before opening WhatsApp.
- Create a canonical unique order number.
- Snapshot server-authoritative product name, SKU, quantity, and price.
- Server calculates all totals; never trust client-supplied prices.
- Return the created order snapshot.
- Build the WhatsApp message from that server response.
- Include order number, customer information, products, quantities, prices, delivery, totals, and customer notes.
- If order creation fails, WhatsApp must not open.
- Protect against double-click/retry duplicates with an idempotency/client-reference mechanism.
- The order appears immediately in admin as a new website order.

### Order editing

Normal `admin` and `super_admin` users may edit incomplete website orders:

- add/remove catalog products
- change quantity
- increase or decrease the order-line unit price
- change discount and delivery fee
- update customer data
- add internal notes
- update allowed order status
- provide a reason for material changes

Every order item must retain its original price and current order-only price. Editing an order must never change catalog/site prices, promotions, or future orders.

Keep an immutable activity trail with actor, timestamp, event type, old value, new value, and reason.

Approved order states:

- `new`
- `reviewing`
- `preparing`
- `out_for_delivery`
- `completed`
- `cancelled`

A cancelled order never creates an invoice.

### Completion and invoices

- An invoice is created only when an employee or manager explicitly completes the order through a final review.
- Final review shows final items, quantities, prices, subtotal, discount, delivery fee, final total, payment method, paid amount, remaining amount, payment details, and internal invoice notes.
- Completion must be one atomic transaction.
- The order becomes locked.
- Create exactly one active internal invoice.
- Invoice and invoice items are immutable snapshots independent of later catalog/order edits.
- Invoice displays final unit prices only.
- No customer invoice sending, PDF, print/share flow, or customer invoice portal.
- Retry/double completion must not create a duplicate active invoice.

Invoice status:

- `active`
- `cancelled`
- `replaced`

### Payment

Payment methods:

- `cash_on_delivery`
- `card`
- `bank_transfer`

Payment statuses:

- `unpaid`
- `partially_paid`
- `paid`
- `partially_refunded`
- `refunded`

Store one primary payment method and free-text payment details. Do not build a detailed multi-payment ledger.

Normal admin may:

- increase paid amount up to invoice total
- progress unpaid → partially paid → paid
- select/update primary payment method
- update payment details

Normal admin may not:

- reduce paid amount
- revert a fully paid invoice
- record refunds
- cancel/replace invoices
- directly edit invoice snapshot values

Manager/super_admin may perform corrections and partial/full refunds, but a non-empty reason and immutable activity log are required.

### Manual orders

Manager/super_admin only:

- create orders originating from WhatsApp, phone, walk-in, social media, or another source
- save incomplete or complete immediately
- add catalog products
- add manual items not present in the catalog
- set manual item name, optional description, quantity, and unit price
- override order-line price

Manual items remain only in that order/invoice. They must not create catalog products, change catalog prices, or affect inventory.

Every invoice must still be linked to an order; do not allow standalone invoices.

### Reopen and replacement

Manager/super_admin only:

- reopen a completed order with a mandatory reason
- retain the old invoice permanently
- mark the old invoice cancelled/replaced
- unlock the order for manager correction
- recomplete it to create a new invoice number
- link old and replacement invoices both directions where practical
- maintain exactly one active invoice
- record actor, reason, timestamps, prior invoice, and replacement invoice

Do not hard-delete final invoices.

## Architecture requirements

- Follow existing FastAPI/SQLAlchemy/Alembic/Pydantic patterns.
- Support both SQLite and MySQL used by this repository.
- Use the project's existing Decimal/money convention; never use binary floating-point for persisted calculations.
- Extend existing tables and models backward-compatibly.
- Backfill legacy order/invoice data safely.
- Preserve IDs and relationships.
- Use backend-enforced role permissions.
- Use transaction boundaries for public create, admin edit, completion, manual complete, payment correction, and reopen/replace.
- Use the repository's existing pagination, filtering, error, auth, and UI patterns.
- Preserve existing inventory behavior for catalog orders; do not invent a new reservation/deduction design.
- Do not add dependencies unless technically necessary and justified.

## Required admin UI

### Orders page

- search by order number, customer name, or phone
- filters for status, source, payment status, and date
- show total, order status, payment status, source, created time
- open customer WhatsApp
- open detail/edit

### Order detail

- customer and source
- original/current item values
- editable items for eligible orders
- order-only price editing
- discount/delivery
- notes and required edit reason
- activity timeline
- state transitions
- completion review dialog

### Invoices page

- search invoice/order/customer
- filters date, payment, source, employee, invoice status
- internal invoice detail with final prices only
- routine payment updates
- manager correction/refund flow
- cancelled/replaced visual state
- links between old and replacement invoices
- no customer PDF/share controls

### Manual order page

- manager-only route and navigation
- source/customer fields
- catalog product search/add
- manual item add
- quantity/price editing
- discount/delivery
- payment/details/notes
- save incomplete or complete and invoice

All UI must be responsive, RTL-safe, accessible by keyboard, and consistent with existing admin components. Backend permissions remain authoritative.

## Testing and verification

Implement task-by-task with failing tests first and small commits. At minimum, cover every acceptance matrix in the plan.

Required final commands:

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

From `frontend`:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

From repository root:

```powershell
git diff --check
git status --short
```

Also:

- test Alembic upgrade from the prior revision using a disposable database containing representative legacy order/invoice data
- verify downgrade behavior for only the newly introduced migration
- run real browser acceptance on desktop and mobile
- prove catalog prices remain unchanged after order edits
- prove manual items do not alter catalog/inventory
- prove retrying completion cannot create two active invoices
- prove permission boundaries with backend API tests, not only hidden buttons

## Required documentation and final report

Create:

- `docs/implementation/order-invoice-current-state.md`
- `docs/implementation/order-invoice-acceptance.md`

Update relevant project docs/routes/API documentation.

Final report must state:

1. exact branch/worktree and commits
2. exact files created/modified
3. exact migration revision and upgrade/downgrade evidence
4. exact API endpoints
5. final role/permission matrix
6. test command outputs and counts
7. browser widths/browser and observed results
8. backup file paths used before local migration
9. proof that catalog prices and manual-item inventory remain isolated
10. proof of one active invoice per completed order
11. any genuine remaining limitation
12. final `git status`

Do not claim success unless all required verification evidence is available. If a test fails, debug the root cause rather than bypassing, weakening, or deleting the test.
