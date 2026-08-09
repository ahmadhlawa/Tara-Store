# Order and Internal Invoice Workflow Implementation Plan

> **For agentic workers:** Execute sequentially with `superpowers:subagent-driven-development`, TDD, per-task review, and final verification.

**Goal:** Replace the legacy confirmation invoice workflow with the approved internal order and invoice workflow without a parallel subsystem.

**Architecture:** Extend `app.models.orders` and `app.models.invoices`, retain their identifiers, and move transaction rules into `app.services.orders` and `app.services.invoices`. Keep FastAPI contracts in `schemas` and the existing public/admin routers; keep React integration in the existing checkout and admin modules.

**Tech stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, SQLite/MySQL, React, JavaScript, Vitest.

## Corrected repository map and interface decisions

1. The authoritative source files supplied outside this worktree are `docs/superpowers/2026-08-03-order-invoice-workflow-design.md` and `docs/superpowers/2026-08-03-order-invoice-workflow-implementation-plan.md`; this tracked file corrects their paths for this branch.
2. The next migration follows `backend/alembic/versions/0004_import_batches.py`, not `0003_invoices`.
3. Existing endpoints are in `admin_commerce.py` and `admin_invoices.py`; preserve their `/api/v1/admin` prefix and extend them with `PATCH /orders/{id}`, `POST /orders/{id}/complete`, `POST /orders/manual`, `POST /orders/{id}/reopen`, `PATCH /invoices/{number}/payment`, and `POST /invoices/{number}/refund`.
4. Existing canonical fields are `Order.product_name`, `sku`, `discount`, and `total`; new fields retain that naming rather than introducing duplicate `name_snapshot`, `discount_amount`, or `total_amount` storage columns.
5. Use `AdminRole.SUPER_ADMIN` as the manager role. `CurrentAdmin` permits routine staff actions; a new explicit manager dependency/helper guards manual, refund, correction, and reopen actions.
6. Replace legacy `pending/confirmed/processing/ready/shipped/delivered` semantics with the approved persisted values. The migration maps `pending` to `new`, `confirmed/processing` to `reviewing`, `ready` to `preparing`, `shipped` to `out_for_delivery`, and `delivered` to `completed`.
7. Remove invoice print/query controls from `OrdersPages.jsx` and `InvoicesPages.jsx`; no customer-facing PDF, print, sharing, email, or WhatsApp invoice feature is retained.

## Execution tasks

- [ ] Add focused failing tests in `backend/tests/test_order_invoice_workflow.py` for schema/migration compatibility, then migrate and extend the existing models.
- [ ] Add failing pure-service tests, then implement Decimal totals, payment derivation, immutable activity events, and role-safe transactional operations.
- [ ] Add public-checkout tests, then add client references and canonical server snapshots in `schemas/orders.py`, `public_checkout.py`, `services/orders.py`, `services/checkout.js`, and `CheckoutRoutePage.jsx`.
- [ ] Add admin order/invoice API tests, then implement editing, final completion, payment changes, manual orders, and reopen/replacement in existing routers/services/schemas.
- [ ] Add frontend tests, then extend `adminApi.js`, `OrdersPages.jsx`, `InvoicesPages.jsx`, `AdminApp.jsx`, and `AdminLayout.jsx` with accessible RTL-safe workflow UI and manager-only controls.
- [ ] Run disposable migration upgrade/downgrade, full suites, browser acceptance, and write `docs/implementation/order-invoice-acceptance.md`.
