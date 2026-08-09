# Backend architecture

A focused modular monolith. One FastAPI application, one database, clear internal seams
where a boundary is likely to move later (storage, database engine).

## Layers

```
app/main.py            application factory: CORS, /health, router, media mount,
                       three exception handlers
    │
app/api/v1/router.py   assembles the endpoint modules under /api/v1
app/api/v1/endpoints/  routing and HTTP concerns only
app/api/deps.py        shared dependencies: session, current admin, super-admin
                       guard, pagination
app/api/crud.py        small generic list/create/update/delete helpers
    │
app/schemas/           Pydantic v2 request and response models — the API contract
app/services/          business rules: pricing, orders, catalog, slugs, audit,
                       store settings, placeholder images, domain errors
app/models/            SQLAlchemy 2.x ORM entities
app/storage/           StorageProvider interface; local disk active, R2 inert
app/db/                engine, session factory, declarative Base
app/core/              settings, enums, password hashing and JWT
```

The dependency direction is one-way: endpoints may use services, schemas and models;
services never import from `api/`.

## Request flow

A checkout request is representative:

1. `POST /api/v1/orders` is matched in `endpoints/public_checkout.py`.
2. FastAPI validates the body into an `OrderCreate` schema.
3. `DbSession` supplies a SQLAlchemy session for the request.
4. The endpoint calls `services/orders.py`, which — inside one transaction — re-reads
   every product from the database, recomputes the subtotal, revalidates the coupon,
   recomputes the delivery fee, decrements stock, writes the `Order`, its immutable
   `OrderItem` snapshots and the first `OrderStatusHistory` row.
5. The response is serialised through an `OrderOut` schema. `public_token` is returned
   exactly once, at creation.
6. Any `DomainError` raised on the way is converted to the standard error body.

## Configuration

`app/core/config.py` holds a single pydantic-settings `Settings` object, read from the
environment and an optional `backend/.env`, cached with `lru_cache`.

Two details are load-bearing:

- **`CORS_ORIGINS` is annotated with `NoDecode`.** pydantic-settings otherwise JSON-decodes
  complex fields inside the env source, before validators run, which made the documented
  comma-separated form in `.env.example` unloadable. The validator accepts both a
  comma-separated string and a JSON list.
- **Relative SQLite paths are anchored to the backend root**, not the process working
  directory, so `alembic`, the seed and the app all resolve `./data/commerce_dev.db` to the
  same file regardless of where they are launched.

## Errors

Every error leaves the API in one shape, produced by three handlers in `main.py`:

```json
{ "error": { "code": "insufficient_stock", "message": "الكمية المطلوبة غير متوفرة." } }
```

Validation failures add a `fields` array of `{field, message}` and use code
`validation_error` with HTTP 422.

Services raise `DomainError` subclasses from `services/errors.py` carrying a status code,
a stable machine-readable `code` and an Arabic message suitable for display. Endpoints
therefore contain almost no error handling of their own, and the frontend can branch on
`code` without parsing prose.

## Authentication and authorisation

- Passwords are hashed with **Argon2** (via `pwdlib`). Plaintext is never stored or logged.
- `POST /auth/login` returns a **JWT (HS256)** signed with `SECRET_KEY`, expiring after
  `ACCESS_TOKEN_EXPIRE_MINUTES`. Invalid credentials produce one generic response, so the
  endpoint does not reveal whether an address exists.
- `get_current_admin` decodes the bearer token and re-loads the account **on every
  request**. Deactivating an administrator therefore invalidates their existing token
  immediately, without a revocation list.
- `require_super_admin` gates admin accounts and audit logs. The API enforces this
  independently of the frontend hiding the navigation entries.
- Self-protection rules live in the service layer: a super admin cannot disable, demote or
  delete itself, and the last active super admin cannot be deleted.

Rotating `SECRET_KEY` invalidates every issued token — the intended way to force all
administrators to sign in again.

## Pricing and order rules

These are the invariants worth protecting:

- **Prices come from the database.** The cart endpoints accept product ids and quantities
  only; there is no field in which a client could submit a price.
- `compare_at_price` is a display-only reference and is never charged.
- Coupons are revalidated server-side on every pricing and checkout call: minimum order,
  maximum discount cap, usage limit and date window. The discount can never exceed the
  subtotal.
- Delivery fees come from the chosen `DeliveryArea`, including its optional free-delivery
  threshold. Inactive areas are rejected.
- Stock is decremented **once**, inside the order transaction, and restored **once** on
  cancellation; repeated cancellation is a no-op, and a cancelled order cannot re-enter a
  stock-holding status. `track_inventory = false` disables enforcement per product.
- Variant stock is authoritative when a variant is selected.
- `OrderItem` rows are immutable snapshots: renaming or repricing a product never rewrites
  history.
- Order confirmation is scoped by `Order.public_token`, returned once at creation. The
  order number alone never reveals an order.

Money is `Numeric(12,2)` in the database and `Decimal` in Python throughout.

## Storage

`app/storage/base.py` defines the `StorageProvider` interface — save, delete, URL
resolution. `LocalStorageProvider` writes into `LOCAL_MEDIA_ROOT` under a random
`uuid4().hex` filename and is mounted at `LOCAL_MEDIA_BASE_URL` by the application.
Uploads are validated by **magic bytes** (JPEG, PNG, WebP, GIF, ICO), not by the supplied
filename or content type, and are size-limited by `MAX_UPLOAD_SIZE_BYTES`.

The database stores metadata and a URL; files are never stored as Base64 or BLOBs.

`R2StorageProvider` is a deliberate, inert boundary: selecting it without credentials
raises a clear configuration error rather than failing silently. See
[future-r2-integration.md](future-r2-integration.md).

## Audit log

`services/audit.py` records product, category, order, coupon, settings, media and admin
changes, plus logins, with the acting administrator and a JSON metadata blob. Credentials
and tokens are stripped before anything is written.

## Database access

`app/db/session.py` builds the engine from `settings.sqlalchemy_url()` and exposes a
request-scoped session dependency. SQLite gets `check_same_thread=False`; the code makes no
other engine-specific assumption.

**Alembic is the schema of record.** `alembic/versions/0001_initial_...py` builds every
table. `Base.metadata.create_all` is used only to construct throwaway test databases.
`tests/test_migrations.py` asserts that the migrated schema and `Base.metadata` describe
exactly the same set of tables, so a model that drifts from the migration is a test
failure rather than a silent production surprise.

## Tests

`backend/tests/` covers auth and roles, catalog, checkout and pricing, content and media,
health and configuration, and migrations. Each test builds its own SQLite database and
overrides the session dependency; nothing touches `commerce_dev.db`.

Current: **74 passed, 88 % coverage**.
