# Full validation fixture

The acceptance fixture is built by `backend/scripts/seed_full_validation.py`. It exists
so that browser validation, destructive CRUD and permission checks never run against a
database anyone cares about.

This document contains no credentials, tokens or personal data. The acceptance accounts
live only inside the disposable database and are useless anywhere else.

## Safety model

- The seeder refuses any `DATABASE_URL` whose file name is not
  `vista_full_validation_<yyyymmdd-hhmmss>.db`. A mistyped argument cannot reach
  `vista_preview.db` or `vista_store_dev.db`.
- The disposable database is a **copy** of the runtime database, upgraded from its
  revision to head. Copying rather than starting empty means the fixture sits next to
  realistic pre-existing data and the legacy upgrade path is exercised for real.
- `*.db` is already ignored by Git, so no validation database is ever committed.
- Re-seeding in place is refused. Migration `0008_order_activity_triggers`
  makes `order_activities` append-only, so a fixture that deleted its own orders would
  be fighting the invariant the run is supposed to prove. A second run starts from a new
  copy, which is what makes the dataset deterministic.

## Building one

```powershell
cd D:\Project\vista-store-e-commerce\backend
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$rel = "data/vista_full_validation_$stamp.db"
Copy-Item "data\vista_preview.db" $rel
$env:DATABASE_URL = "sqlite+pysqlite:///./$rel"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed_full_validation.py --database-url "sqlite+pysqlite:///./$rel"
```

Catalog, content, marketing and account rows are written through the ORM. **Orders and
invoices are created through the real HTTP API** using an in-process TestClient bound to
the same engine, so invoice numbering, the one-active-invoice constraint, activity
records and the issuer snapshot are all produced by production code paths rather than by
hand-written SQL.

## What it creates

### Accounts

| Marker | Role | Active | Purpose |
| --- | --- | --- | --- |
| `super@vista-acceptance.dev` | `super_admin` | yes | manager-only screens and actions |
| `admin@vista-acceptance.dev` | `admin` | yes | permission-boundary checks |
| `inactive@vista-acceptance.dev` | `admin` | no | deactivated-account login rejection |

### Catalog

Four categories (`vfx-resin`, `vfx-molds`, `vfx-packages`, and one deliberately
inactive), and nine products covering: two in the same category, a discounted product
that surfaces in `/offers`, a product with several images, one with no image at all, a
low-stock product, an out-of-stock product, an inactive product that must never appear
publicly, a very long Arabic name, and two products sharing a display name but holding
distinct ids and slugs.

### Content

Three hero slides (one inactive), three banners across three placements (one inactive),
two articles (one unpublished), two static pages (one unpublished), and store settings
carrying phone, WhatsApp, email, address and working hours so the contact and checkout
screens have something real to render.

### Promotions and delivery

Five coupons — a valid percentage coupon with a cap, a valid fixed coupon with a
minimum, an expired one, one whose usage limit is already exhausted, and a disabled one.
Four delivery zones — two priced, one free, one inactive.

### Orders

Twenty-one orders, covering every canonical status (`new`, `reviewing`, `preparing`,
`out_for_delivery`, `completed`, `cancelled`) and every source (`website`, `whatsapp`,
`phone`, `walk_in`, `social`, `other`, the last with the mandatory source note). Also
covered: an order with a coupon and multiple lines, a manual-items-only order containing
two rows that share a name, a mixed catalog/manual order with an order-only price
override plus a discount and a delivery fee, and a manual order completed at creation.

### Invoices

Nine invoices covering all three statuses and all five payment statuses:

| Scenario | Status | Payment |
| --- | --- | --- |
| completed website order | active | unpaid, bank transfer |
| completed website order | active | paid, card |
| employee-recorded part payment | active | partially paid, cash |
| manager partial refund | active | partially refunded |
| manager full refund | active | refunded |
| superseded by a reopen cycle | replaced | — |
| replacement issued after the reopen | active | partially paid |
| legacy record (see below) | cancelled | — |
| manual walk-in completed at creation | active | paid |

### The one row written by hand

The `cancelled` invoice is set directly rather than through the API, and is marked as
such in the seeder. There is no API path that reaches this state today: an invoice only
exists once its order is completed, and `POST /admin/invoices/{number}/cancel` then
refuses with `order_locked` — which the backend suite asserts on purpose. The archive
screen still offers `cancelled` as a filter for rows written before completion locked
orders, so the fixture provides one for that filter to match. Nothing in this repository
should be read as evidence that cancelling from the invoice screen works; it does not.

## Expanded validation use (2026-08-07)

`vista_full_validation_20260806-041041.db` was used for focused Playwright work only.
Catalog records use timestamped slugs and are deleted in `finally`; checkout orders
remain in this disposable file. No preview database is part of those checks.
The corresponding isolated server must set `LOCAL_MEDIA_ROOT` to
`./data/vista_full_validation_20260806-041041_uploads`; the default `vista-uploads`
directory causes public media 404s.
This fixture exists for local development validation only and does not represent final
production media storage or deployment configuration.

## Boundary data included

Arabic and English text, mixed Arabic/English product names, long-but-valid names, zero
discounts, empty optional notes, duplicate-looking names with distinct ids, and manual
line items sharing a name but holding separate row identities. No row violates a current
database constraint.
