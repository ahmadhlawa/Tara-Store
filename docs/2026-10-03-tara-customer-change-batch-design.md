# Tara Gallery Customer Change Batch — Design Specification

**Date:** 2026-10-03  
**Project:** the-taragallery / Tara-Store  
**Repository:** `ahmadhlawa/Tara-Store`  
**Rule:** local implementation and review first; no Production changes in this stage.

## 1. Scope and delivery strategy

Implement the approved customer changes in three reviewable batches:

1. **Storefront:** header, sale badge, packaging, homepage source of truth.
2. **Orders & Invoices:** simplified statuses/payment, completed-order editing, invoice lifecycle, inventory deltas.
3. **Analytics:** clearer charts, session duration, funnel and abandoned-cart aggregates.

Each batch must keep tests green before moving to the next.

---

## 2. Storefront

### 2.1 Unified header

- Replace the circular Tara logo in both mobile and desktop storefront headers with the fixed wordmark `TARA`.
- `TARA` is always uppercase, bold, and color `#d7cae8`.
- It is brand identity, not translated content, so it stays exactly `TARA` in Arabic and English.
- Remove `Handmade by Yumna` from the desktop header.
- Preserve existing navigation, search, cart, language switch, menu behavior, and mobile hit targets.

### 2.2 Sale badge

- Replace every customer-facing numeric discount percentage badge with the fixed label `%تخفيض`.
- Keep the current sale styling unless a small layout adjustment is needed.
- Product detail keeps the current old struck-through price + new price display.
- Do **not** add savings amount text.
- Numeric discount percentage remains Admin-only.
- Do not change pricing logic.

### 2.3 Packaging

Add an order-level packaging choice at the end of the cart:

- `تغليف عادي` → 0 ₪
- `تغليف كهدية` → +5 ₪ per order

Requirements:

- Backend is authoritative for the 5 ₪ fee; client cannot submit an arbitrary fee.
- Persist packaging type and packaging fee on the order.
- Show both in cart/checkout summary, Admin order detail/edit, and invoice.
- Admin can change packaging later; totals recalculate automatically.
- Recommended stored values: `normal` and `gift`; translate only in presentation.

### 2.4 Homepage source of truth

- Homepage renders only Admin-managed Home Sections.
- Remove the legacy automatic homepage showcase path based on category `show_on_home`.
- Prevent old demo/default sections from resurfacing just because product flags later match featured/new/bestseller logic.
- Preserve generic Home Section types that Admin intentionally creates.
- Change seed/default behavior so obsolete demo rows are not recreated.
- Do not silently delete Production HomeSection rows in an unrelated migration. Prepare a deliberate cleanup step for reviewed legacy rows at deployment time.

---

## 3. Orders and invoices

### 3.1 Canonical order statuses

Only these four statuses are selectable going forward:

- `new` → طلب جديد
- `ready` → جاهز
- `completed` → مكتمل
- `cancelled` → ملغى

Normalize existing data:

- `confirmed` → `ready`
- `delivered` → `completed`

Other legacy aliases should map to the closest canonical status and remain readable, but not selectable.

### 3.2 Invoice issuance

- No invoice at order creation.
- No invoice at `ready`.
- Issue an invoice only when the order becomes `completed` and no active invoice exists.
- A `cancelled` order has no active invoice.

### 3.3 Editing completed orders

Completed orders remain editable.

Before editing/saving a completed order, show a strong warning such as:

> هذا الطلب مكتمل وتم تسجيل بياناته وفاتورته في النظام. أي تعديل من الآن قد يغيّر البيانات المالية أو المخزون. تأكد من التعديلات قبل الحفظ، وأنت مسؤول عن صحة البيانات الجديدة.

Buttons:

- إلغاء
- موافق، متابعة التعديل

Allow editing customer data, address, notes, items, options/variants, quantities, unit prices where current Admin rules permit, discount, delivery fee, packaging, payment state, and existing editable metadata.

Record stable before/after business values in the activity log for completed-order mutations.

### 3.4 Invoice behavior while order stays completed

If an order remains `completed` while edited:

- keep the same invoice row and invoice number,
- update that current invoice snapshot to match the edited completed order,
- update lines, totals, customer snapshot, packaging, and payment fields as needed,
- record the change in activity history.

Do not create a replacement invoice merely because a completed order was edited.

### 3.5 Leaving completed state

If `completed → ready/new`:

- archive/cancel the current invoice without deleting it,
- it is no longer active,
- preserve its number and history,
- when the order later becomes `completed` again, issue a new invoice number.

If `completed → cancelled`:

- show a confirmation warning,
- return committed stock,
- cancel/archive the active invoice,
- preserve historical invoice data,
- record the transition in activity log.

---

## 4. Payment workflow

Admin uses only:

- `unpaid` → غير مدفوع
- `paid` → مدفوع
- `refunded` → مردود

The primary UI should be a direct state selector, not a complex paid/refunded amount editor.

For invoice total `T`:

- **unpaid:** paid=0, refunded=0, remaining=T
- **paid:** paid=T, refunded=0, remaining=0
- **refunded:** paid=T, refunded=T, remaining=0

Correction reason is optional. If provided, save it in activity/audit history; absence must not block saving.

Do not require super-admin solely to switch among these three payment states if the Admin is otherwise authorized to manage the order/invoice.

When a completed invoice total changes after an edit:

- if `paid`, keep it paid and set paid amount to the new total;
- if `unpaid`, keep paid amount 0 and update remaining amount;
- if `refunded`, keep it fully refunded against the new total.

Record automatic monetary adjustments in activity history.

---

## 5. Inventory behavior during Admin edits

### 5.1 Difference-based stock adjustment

Adjust stock by delta rather than replaying the whole order:

- quantity 2 → 3: subtract 1
- quantity 3 → 1: return 2
- remove line: return its committed quantity
- add line: subtract its quantity
- change product/variant: return old commitment and subtract new commitment

Completed orders remain stock-committing orders, so edits affect stock immediately.

### 5.2 Negative stock override

Admin may save even if the edit makes tracked stock negative.

Before save, show:

> الكمية المطلوبة أكبر من المخزون المتوفر حاليًا، واستمرار التعديل سيجعل المخزون بالسالب. هل تريد المتابعة؟

Buttons:

- إلغاء
- متابعة وحفظ

This must have an explicit backend override path; do not rely on client-only confirmation.

The current DB has non-negative constraints on product and variant stock, so implementation must include a deliberate SQLite/MySQL migration to remove/replace those constraints.

Public checkout **must still block** overselling tracked stock. Negative stock is an Admin override only.

Any Admin action that creates negative stock should be recorded in activity/audit history.

---

## 6. Analytics

### 6.1 Goal

Keep Analytics compact and useful, not a per-visitor surveillance tool.

Keep periods:

- today
- last 7 days
- last 30 days

### 6.2 Summary cards

Show:

- visits/sessions
- unique visitors
- average session duration
- completed orders

Average duration can be calculated from existing `started_at` and `last_activity_at`.

### 6.3 Charts

- Keep approximate visitor locations, shown once as a clean ranked chart.
- Show top products once as a clean ranked chart with view counts.
- Remove the current duplication where top products appear as both chart and repeated ranking list.

### 6.4 Funnel

Show an aggregated funnel:

1. product view
2. add to cart
3. checkout reached
4. order completed

Show counts and/or conversion percentages only; no per-user drill-down.

### 6.5 Abandoned carts

Show one aggregate abandoned-cart metric.

Use a deterministic definition, e.g. a session with at least one add-to-cart event, no completed order, and older than the session timeout/abandonment window. Document and test the final rule.

### 6.6 Tracking additions

Current analytics already has sessions/location/product views. Add only the minimum events required:

- `add_to_cart`
- `checkout_reached`
- `order_completed`

Requirements:

- anonymous session association only,
- no name/email/phone in analytics events,
- no IP persistence,
- reuse current visitor/session cookie model,
- preserve rate limits and same-origin protection,
- preserve existing trusted Cloudflare location/proxy-token behavior.

New funnel metrics start from deployment onward. Do not fabricate historical funnel data from product views.

---

## 7. Expected schema/migration work

Expected changes include:

- Order packaging type and packaging fee.
- Invoice packaging snapshot/fee where needed.
- Mutable current active invoice support for completed-order edits.
- Order-status normalization migration.
- Removal/replacement of non-negative stock constraints for product/variant stock.
- Analytics event persistence for the funnel.

Migrations must pass both SQLite and MySQL 8 gates.

Do not hide destructive Production cleanup inside unrelated migrations.

---

## 8. Server-authoritative calculations

Backend remains authoritative for:

- item prices,
- coupon/discount,
- delivery fee,
- 5 ₪ gift packaging fee,
- order totals,
- invoice totals,
- payment money fields,
- stock delta.

Never trust the browser to send final totals or an arbitrary packaging charge.

---

## 9. Compatibility and safety

- Existing historical orders/invoices remain readable.
- Do not delete invoice history.
- Preserve storefront stock privacy: no exact stock count in normal browsing.
- Sold-out behavior continues when inventory tracking is enabled.
- Public checkout continues enforcing tracked stock limits.
- No R2 bucket-wide migration/deletion/cleanup in this batch.
- No Production changes until local validation, review, explicit GitHub write approval, green CI, and explicit deployment approval.

---

## 10. Required tests

### Storefront
- `TARA` on mobile/desktop and unchanged by locale.
- removed desktop tagline.
- `%تخفيض` badge, old/new prices unchanged.
- normal/gift packaging totals and persistence.
- server rejects arbitrary packaging fee manipulation.
- Home renders only Admin Home Sections, not legacy category showcases.

### Orders/invoices
- four canonical statuses and migration mapping.
- invoice issued only on completed.
- completed edit warning.
- same invoice number updated while order remains completed.
- leaving completed archives invoice; returning to completed creates new invoice.
- completed → cancelled restores stock and archives invoice.
- three payment states and optional correction reason.
- payment fields recalculate correctly after total changes.
- before/after activity recording.

### Inventory
- quantity/add/remove/change-item deltas.
- Admin negative-stock override works on SQLite and MySQL.
- public checkout still rejects unavailable tracked stock.

### Analytics
- summary cards and average duration.
- one location chart.
- one top-products chart without duplication.
- funnel event recording.
- abandoned-cart calculation.
- anonymous-only analytics payloads.
- today/7d/30d boundaries.
- existing location behavior preserved.

---

## 11. Out of scope

Do not expand this batch into unrelated backlog work such as auth hardening, delivery-area redesign, coupon concurrency redesign, R2 cleanup, server upgrades, full storefront redesign, or payment-gateway integration.
