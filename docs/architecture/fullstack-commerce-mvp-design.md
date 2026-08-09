# Full-stack commerce MVP — design

Status: implemented on `feat/fullstack-commerce-mvp`.

## 1. Product model

One running instance == one store. No multi-tenancy, no `tenant_id`, no shared SaaS
database. Each future client gets its own code checkout, database, environment file,
service, domain and admin accounts. The template carries no client branding.

## 2. Shape of the system

```
frontend (React 18 + Vite 6, JS/JSX, Arabic RTL)
    │  fetch  /api/v1/...            (Bearer JWT for /api/v1/admin/*)
    ▼
backend (FastAPI, modular monolith)
    ├── api/v1        routing + request/response schemas
    ├── services      business rules (pricing, orders, inventory, audit, slugs)
    ├── models        SQLAlchemy 2.x ORM
    ├── storage       media provider interface (local active, R2 adapter inactive)
    └── db            engine/session; Alembic owns the schema
    ▼
SQLite (local dev/tests)  →  MySQL 8 later, same models, via DATABASE_URL
```

Everything money-related is computed server-side. The client never sends totals.

### Why a modular monolith

The whole surface is one store's catalog, content and orders. Splitting it into
services would add deployment cost with no isolation benefit, and the target
deployment is one `uvicorn` process per client behind Nginx.

## 3. Backend decisions

| Decision | Rationale |
| --- | --- |
| `Numeric(12, 2)` + Python `Decimal` for money | avoids float drift; identical on SQLite and MySQL 8 |
| Status/role/type stored as `String(32)` validated by Pydantic enums | portable; avoids native-ENUM migration pain on MySQL |
| Naive UTC `DateTime` columns, serialized with a `Z` suffix | MySQL `DATETIME` friendly; one timezone in the system |
| `JSON` column only for `HomeSection.config` | the only place where a grouped, schema-light payload is genuinely simpler |
| Alembic is the schema source of truth | `create_all` is only used to build throwaway test databases |
| JWT (PyJWT, HS256) + Argon2 (pwdlib) | stateless admin auth, no session store to operate |
| Order snapshots (`OrderItem`, delivery/coupon fields) | orders stay readable after a product is edited or disabled |

### Server-authoritative checkout

`services/pricing.py` and `services/orders.py` own the rules:

1. Load every referenced product/variant from the database; reject inactive ones.
2. Take unit price from the DB (`price`, or the variant override) — never
   `compare_at_price`, never a client-supplied price.
3. Sum the subtotal from DB prices × requested quantities.
4. Validate the coupon (active, in window, usage limit, minimum order) and compute
   the discount, capped by `max_discount_amount` and by the subtotal.
5. Look up the delivery area, apply its fee, or 0 when the free-delivery threshold
   is met.
6. `total = subtotal - discount + delivery_fee`, floored at 0.
7. Inside one transaction: decrement inventory, increment coupon usage, write the
   order, its items and the initial status-history row.

Cancellation reverses inventory exactly once — the guard is the order's current
status, so a second cancel is a no-op rather than a second restock.

### Inventory

`track_inventory` toggles enforcement per product. When a product has variants, the
variant's `stock_quantity` is authoritative and the parent product is decremented as
well, so listing-level stock stays meaningful.

## 4. Media

`storage/base.py` defines `StorageProvider` (`save`, `delete`, `url_for`).
`LocalStorageProvider` writes to `LOCAL_MEDIA_ROOT` and serves the files through the
FastAPI app at `LOCAL_MEDIA_BASE_URL`. `R2StorageProvider` implements the same
interface but raises a clear configuration error until R2 credentials are supplied —
the adapter boundary exists, the integration is deliberately not active.

Uploads are validated on content, not on the file name: the magic bytes must match
one of JPEG/PNG/WebP/GIF/ICO, and the size must be under `MAX_UPLOAD_SIZE_BYTES`.
Stored names are `uuid4().hex` + a canonical extension, so uploads cannot collide or
traverse. The database stores metadata and a URL, never bytes.

## 5. Frontend decisions

The existing storefront is preserved. Its presentational components consume a single
decorated view-model (`v`) — that indirection is exactly what lets the data source be
swapped without touching the design, so it is kept.

- Routing moves from `window.location.hash` to React Router `BrowserRouter`.
  `utils/A.jsx` renders a router `<Link>` for internal paths and a plain `<a>` for
  `http(s):`, `tel:`, `mailto:` and `target="_blank"` links, so the markup in the
  design components changes only by tag name.
- `store.js` is reduced to presentation constants (nav links, footer link groups,
  trust features, tone gradients). All commercial data now comes from
  `src/services/*`, which call `src/api/*`.
- Products without an uploaded image fall back to the design's deterministic tone
  gradient (`utils/placeholder.js`), so the storefront looks identical before any
  media is uploaded. Once an image exists, `bg` becomes `url(...) center/cover`.
- Store identity (name, logo, colors, contact, social, SEO) comes from
  `StoreSettings`; colors are applied as CSS custom properties on `:root`.
- The cart stays in `localStorage`; at checkout the server re-prices every line, so a
  stale cart cannot produce a wrong order.

### Admin

`src/admin/` is a separate React Router subtree under `/admin`, with its own layout,
its own Arabic RTL styling and no storefront chrome. Auth state lives in
`storage/authStorage.js`; a 401 from the API clears it and returns to the login page.
`super_admin`-only areas (admins, audit log) are hidden from normal admins in the
navigation and enforced again by the API.

## 6. Testing

Backend tests run against a per-test temporary SQLite file with `create_all`, plus one
test that runs the real Alembic upgrade against a clean database. Frontend tests use
Vitest + React Testing Library + jsdom with `fetch` stubbed — no network, no MySQL, no
R2, no production API.

## 7. Deliberate non-goals

Customer accounts, online card payments, multi-currency, multi-warehouse inventory,
product reviews persisted in the database, and any form of multi-tenancy.
