# Tara Storefront Customer Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved storefront header, customer-facing sale badge, order-level gift packaging, and Home Sections-only homepage behavior without changing unrelated storefront behavior.

**Architecture:** Keep the existing React/FastAPI boundary. Branding and sale-label changes stay presentation-only. Packaging becomes a server-authoritative order-level pricing input persisted on orders and snapshotted to invoices. The homepage removes the legacy `show_on_home` showcase path and renders only Admin-managed Home Sections.

**Tech Stack:** React 18, Vite, Vitest, FastAPI, SQLAlchemy, Alembic, SQLite tests, MySQL 8 production gate.

**Spec:** `docs/superpowers/specs/2026-10-03-tara-customer-change-batch-design.md`

## Global Constraints

- Wordmark is exactly `TARA`, uppercase, bold, color `#d7cae8`, identical in Arabic and English.
- Remove the circular storefront logo and visible desktop tagline/`Handmade by Yumna` from the public header.
- Preserve menu, search, cart, language switch, navigation, accessibility labels, and touch targets.
- Customer-facing sale badge text is exactly `%تخفيض`; do not add a savings amount and do not alter pricing logic.
- Packaging identifiers are `normal` and `gift`; `normal = 0.00`, `gift = 5.00` ₪ per order.
- The backend computes packaging fee; the browser never submits a trusted arbitrary fee.
- Homepage renders only Admin-managed Home Sections; no automatic category `show_on_home` showcases.
- Do not silently delete Production HomeSection data in a migration or startup hook.
- No dependency upgrades or new chart/UI library for this batch.
- No GitHub push and no Production deployment in this plan.

## Review Focus

- Locale switch must never translate or replace `TARA`; Task 1 pins this with a frontend test.
- A malicious client must not be able to force a packaging fee other than the server-defined `0.00` or `5.00`; Task 2 pins this at API/service level.
- Coupon, delivery, and packaging must be combined exactly once in the server total; Task 2 tests the full formula.
- Existing rows must migrate safely to `normal` / `0.00`; Task 2 covers migration defaults.
- Homepage must not call or render legacy `/home-showcases` content even when categories still carry `show_on_home=true`; Task 4 adds a regression test.

---

## File Map

### Frontend

- Modify: `frontend/src/components/public/shell/Header.jsx` — fixed `TARA` wordmark.
- Modify: `frontend/src/index.css` — desktop/mobile wordmark sizing and removal of obsolete logo-layout styling where safe.
- Modify: `frontend/src/utils/productView.js` — public sale badge copy.
- Modify: `frontend/src/app/StoreProvider.jsx` — order-level packaging selection state.
- Modify: `frontend/src/services/checkout.js` — quote/order payload and packaging response mapping.
- Modify: `frontend/src/components/public/cart/CartDrawer.jsx` — packaging selector at end of cart.
- Modify: `frontend/src/pages/CheckoutRoutePage.jsx` — packaging summary, quote, and order placement.
- Modify: `frontend/src/pages/OrderSuccessRoutePage.jsx` — packaging summary if this screen renders the order charge breakdown.
- Modify: `frontend/src/pages/HomePage.jsx` — remove legacy category showcase flow.
- Modify: `frontend/src/services/catalog.js` — remove `homeShowcases()` if no caller remains.
- Modify: `frontend/src/api/publicApi.js` only if the legacy client method becomes dead code and repository convention favors removing it.
- Test: existing `frontend/src/test/localization.test.jsx`, `frontend/src/test/productCards.test.jsx`, `frontend/src/test/storefront.test.jsx`, checkout/cart tests; add a focused packaging test file if needed.

### Backend

- Modify: `backend/app/core/enums.py` — add `PackagingType` (`normal`, `gift`) if that matches project conventions.
- Modify: `backend/app/models/orders.py` — persist `packaging_type`, `packaging_fee`.
- Modify: `backend/app/models/invoices.py` — snapshot `packaging_type`, `packaging_fee`.
- Modify: `backend/app/schemas/orders.py` — quote/order/admin fields.
- Modify: `backend/app/schemas/invoices.py` — invoice fields.
- Modify: `backend/app/services/pricing.py` — authoritative packaging fee in pricing.
- Modify: `backend/app/services/orders.py` — persist packaging values.
- Modify: `backend/app/services/invoices.py` — copy packaging snapshot when issuing an invoice.
- Modify: `backend/app/api/v1/endpoints/public_checkout.py` — accept packaging type in quote/order APIs, never an arbitrary fee.
- Create: next Alembic migration from the actual current head — add packaging columns with safe defaults.
- Inspect and modify the current instance/bootstrap source that seeds Home Sections; find it by searching for `HomeSection`, `section_key`, `featured`, `new`, `bestsellers`, and `packages`.
- Test: `backend/tests/test_checkout.py`, `backend/tests/test_invoices.py`, `backend/tests/test_migrations.py`, and matching instance/bootstrap tests.

---

### Task 1: Fixed `TARA` Header and Public Sale Badge

**Interfaces:**
- Consumes: store settings only for accessible home-link context; visible brand text is not sourced from settings.
- Produces: literal visual wordmark `TARA`; public `productBadges(view)` emits `%تخفيض` for sale products.

- [ ] **Step 1: Write failing frontend tests**
  - Add assertions that the public header renders visible text exactly `TARA` in Arabic and English.
  - Assert the public header no longer renders the circular store-logo image.
  - Assert the visible tagline is absent.
  - Assert changing locale leaves `TARA` unchanged.
  - Assert a sale card badge is `%تخفيض` while the old and current prices remain unchanged.

- [ ] **Step 2: Run the focused tests and verify failure**
  - Run: `cd frontend && npm test -- --run src/test/localization.test.jsx src/test/productCards.test.jsx`
  - Expected: new assertions fail against current logo/store-name/percentage behavior.

- [ ] **Step 3: Implement the fixed wordmark**
  - In `Header.jsx`, simplify `StoreMark` so the visible brand is literal `TARA`.
  - Remove `useLogoFit` and decorative header-logo image markup if no longer used there.
  - Keep a localized accessible home-link label if useful, but do not translate the visible wordmark.
  - In `index.css`, make the wordmark bold, `#d7cae8`, and appropriately sized on mobile and desktop without moving or shrinking existing controls.

- [ ] **Step 4: Implement fixed customer sale copy**
  - In `productView.js`, keep any numeric discount calculation needed elsewhere, but make the public badge label `%تخفيض`.
  - Do not change `priceText`, `oldText`, `sale`, `price`, or compare-at-price rules.

- [ ] **Step 5: Run focused tests, then the full frontend suite**
  - Run: `cd frontend && npm test`
  - Expected: PASS.

- [ ] **Step 6: Commit locally**
  - `git add frontend/src/components/public/shell/Header.jsx frontend/src/index.css frontend/src/utils/productView.js frontend/src/test`
  - `git commit -m "feat: unify storefront branding and sale badge"`

---

### Task 2: Server-Authoritative Packaging Pricing and Persistence

**Interfaces:**
- Produces: `PackagingType` with `normal|gift`; order/invoice `packaging_type`; monetary `packaging_fee`; cart quote accepts `packaging_type`.
- Later tasks consume persisted packaging when editing completed orders/invoices.

- [ ] **Step 1: Write failing backend tests**
  - Quote with `normal` returns `packaging_fee == 0.00`.
  - Quote with `gift` returns `packaging_fee == 5.00` and total increases exactly 5.00.
  - Assert formula: `total = subtotal - discount + delivery_fee + packaging_fee`.
  - Order creation persists selected type and authoritative fee.
  - Client cannot set an arbitrary packaging fee; reject or ignore such a field according to existing strict-schema conventions.
  - Invoice issuance snapshots packaging type/fee.
  - Migration gives existing orders/invoices safe `normal` / `0.00` values.

- [ ] **Step 2: Run focused backend tests and verify failure**
  - Run: `cd backend && pytest tests/test_checkout.py tests/test_invoices.py tests/test_migrations.py -q`
  - Expected: packaging assertions fail before implementation.

- [ ] **Step 3: Add enum/model/schema/migration support**
  - Add stable packaging identifiers.
  - Add non-null order and invoice packaging columns with safe defaults.
  - Generate the next Alembic revision from the actual current head; do not assume a revision number.
  - Make the migration valid for both SQLite and MySQL 8.

- [ ] **Step 4: Extend server pricing**
  - Extend `price_cart(..., packaging_type=...) -> PricedCart` using the existing service style.
  - `normal` maps to `0.00`; `gift` maps to `5.00`.
  - Include type/fee in `PricedCart` and quote response.
  - Public quote/order requests accept only the type, never a trusted fee.

- [ ] **Step 5: Persist order and invoice snapshots**
  - Extend `OrderDraft` and order creation to store priced packaging values.
  - Extend invoice issuance to copy the order packaging snapshot.

- [ ] **Step 6: Run focused tests, then full backend suite**
  - Run: `cd backend && pytest -q`
  - Expected: PASS except existing documented xfails.

- [ ] **Step 7: Commit locally**
  - `git commit -m "feat: add order packaging choice"`

---

### Task 3: Packaging UI and Checkout Integration

**Interfaces:**
- Consumes: quote response `packaging_type`, `packaging_fee`; order create request accepts `packaging_type`.
- Produces: StoreProvider/checkout state defaulting to `normal`.

- [ ] **Step 1: Write failing frontend tests**
  - Cart displays a final section titled `التغليف`.
  - Options are normal and gift, with gift visibly `+5 ₪`.
  - Default is normal.
  - Selecting gift sends only `packaging_type: "gift"` to quote/order APIs.
  - Summary uses the server-returned packaging fee and total.
  - Placed order preserves the selected packaging type.
  - Locale rendering changes labels only, never stored identifiers.

- [ ] **Step 2: Run relevant cart/checkout tests and verify failure**

- [ ] **Step 3: Add order-level packaging state**
  - Keep it with checkout/cart state in `StoreProvider` following existing conventions.
  - Do not calculate the authoritative final fee in the browser.

- [ ] **Step 4: Implement CartDrawer and checkout UI**
  - Add single-choice packaging selector at the end of the cart.
  - Include packaging type in quote and order calls.
  - Display the server-returned fee in the totals breakdown.
  - Add packaging to WhatsApp/order-success summaries only where those surfaces already list order charges.

- [ ] **Step 5: Run frontend suite and build**
  - `cd frontend && npm test`
  - `cd frontend && npm run build`
  - Expected: PASS.

- [ ] **Step 6: Commit locally**
  - `git commit -m "feat: add packaging checkout UI"`

---

### Task 4: Make Home Sections the Only Homepage Source

**Interfaces:**
- Consumes: `storefrontService.homeSections()` as the only dynamic section list.
- Produces: no automatic category showcase rendering from `show_on_home`.

- [ ] **Step 1: Write failing frontend regression tests**
  - Mock visible Home Sections plus categories with `show_on_home=true`.
  - Assert only Home Sections render.
  - Assert `catalogService.homeShowcases()` is not called.
  - Assert a Home Section intentionally configured as featured/new/bestseller still renders its configured type.

- [ ] **Step 2: Run focused storefront tests and verify failure**

- [ ] **Step 3: Remove the legacy frontend flow**
  - Delete `homeCategories`, home-showcase fetching/state, `renderedShowcases`, and final showcase rendering from `HomePage.jsx`.
  - Remove `catalogService.homeShowcases()` if it has no remaining caller.
  - Remove only dead public client code; do not remove backend compatibility endpoints merely for cleanup unless tests establish that it is safe.

- [ ] **Step 4: Audit default/instance seeding**
  - Search the repository for the code that creates default `HomeSection` rows.
  - Stop obsolete demo/default rows from being recreated automatically in production-like instances.
  - Preserve normal HomeSection CRUD and intentionally Admin-created rows.
  - Do not add a migration that blindly deletes existing Production rows.
  - Produce a short deployment note listing the exact legacy Production rows that may need explicit cleanup later.

- [ ] **Step 5: Run instance/bootstrap and storefront tests**
  - Run matching backend instance/bootstrap tests and full backend suite.
  - Run frontend storefront tests, full frontend suite, and build.

- [ ] **Step 6: Commit locally**
  - `git commit -m "fix: make home sections the homepage source"`

---

### Task 5: Batch A Verification

- [ ] Run `git diff --check`.
- [ ] Run `cd frontend && npm test && npm run build`.
- [ ] Run `cd backend && pytest -q`.
- [ ] Run the repository's MySQL 8 gate exactly as CI defines it; do not improvise against Production.
- [ ] Run Alembic upgrade smoke on a disposable SQLite DB and the repository's MySQL migration gate.
- [ ] Record the actual Alembic head/revision created.
- [ ] Summarize changed files, tests, migration, and any compatibility code kept intentionally.
- [ ] **STOP. Do not push and do not deploy.**
