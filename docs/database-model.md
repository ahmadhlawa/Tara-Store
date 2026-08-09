# Database model

**24 tables**, created by two Alembic revisions — `0001_initial` (the commerce schema) and
`0002_instance_metadata` (instance provenance). Models live in `backend/app/models/`.

## Conventions

| Concern | Decision |
| --- | --- |
| Money | `Numeric(12, 2)` in the database, `Decimal` in Python — never float |
| Enum-like values | `String(32)` validated by Pydantic enums, not native database ENUMs, so MySQL needs no ENUM migrations |
| Timestamps | Naive UTC `DateTime`, serialised with a `Z` suffix |
| JSON | Only `home_sections.config`, `audit_logs.meta` and `instance_metadata.enabled_features` |
| Primary keys | Integer surrogate keys throughout |
| Slugs | Unique, generated from the name, collision-suffixed; Arabic names produce Arabic slugs |
| Deletes | Real deletes; there is no soft-delete column. Orders are never deleted by the app |

## Tables by area

### Administration

**`admin_users`** (9 columns) — email, Argon2 password hash, full name, `role`
(`super_admin` / `admin`), `is_active`, timestamps, `last_login_at`. Deactivating an
account invalidates its existing tokens on the next request, because the account is
re-loaded per request.

**`audit_logs`** (8) — `admin_user_id` → `admin_users.id`, action, entity type and id, a
JSON `meta` blob and a timestamp. Credentials and tokens are stripped before writing.

### Store configuration

**`store_settings`** (27) — a single row: identity, tagline, contact details, social
links, currency, brand colours, SEO fields, `maintenance_mode` and
`order_notifications_email`. The public projection excludes `id` and
`order_notifications_email`. Defaults live in `STORE_SETTINGS_DEFAULTS` in
`app/models/store.py` and are applied both as column defaults and when returning the
unsaved fallback, so a store with no settings row still renders.

### Catalog

**`categories`** (11) — self-referencing `parent_id` → `categories.id`, so categories nest
one or more levels.

**`products`** (24) — `category_id` → `categories.id`; name, slug, SKU, descriptions,
`product_type` (standard / package / mold), `price`, `compare_at_price`, `cost_price`,
`stock_quantity`, `track_inventory`, `low_stock_threshold`, the `is_active` /
`is_featured` / `is_new` / `is_bestseller` flags, sort order, SEO fields, and
`search_text`.

`search_text` holds an Arabic-normalised copy of name + SKU + short description, refreshed
on every write, so `LIKE` search tolerates spelling and diacritic variation. It is
maintained by the catalog service, not by a database trigger.

**`product_images`** (6) — `product_id`, URL, alt text, sort order, `is_primary`.

**`product_specifications`** (5) — ordered label/value pairs.

**Options and variants** — a small four-table EAV:

```
product_options (name)  →  product_option_values (value)
product_variants (sku, price, stock)  →  product_variant_option_values (join)
```

`product_variant_option_values` maps a variant to one value per option, which is how "size
M, colour red" becomes a single stock-keeping row. When a variant is selected, **its**
stock and price are authoritative.

**`package_items`** (6) — `package_product_id` and `included_product_id`, both → `products.id`,
with quantity, display note and sort order. A database-level check forbids
`package_product_id = included_product_id`, so a package cannot contain itself.

### Marketing and content

**`hero_slides`** (13), **`banners`** (12) — image, text, link, placement, sort order and
optional schedule windows; expired entries are filtered out on the public endpoints.

**`home_sections`** (10) — `section_key`, `section_type`, title, description, sort order,
visibility and a JSON `config`. This table decides what the home page contains.

**`coupons`** (14) — code, discount type (percentage / fixed) and value, minimum order,
maximum discount cap, usage limit, usage counter, validity window, `is_active`.

**`delivery_areas`** (10) — name, fee, optional minimum order, optional free-delivery
threshold, `is_active`.

**`articles`** (14), **`static_pages`** (10) — slug, title, body, SEO fields and
publication state. Unpublished records are invisible to the public endpoints.

### Orders

**`orders`** (20) — `delivery_area_id` → `delivery_areas.id`; human-readable
`order_number` in the form `ORD-YYMMDD-NNNN`, `public_token`, status, customer name /
phone / optional email / address, `subtotal`, `discount`, `delivery_fee`, `total`, coupon
code, payment method (`cash_on_delivery` or `manual` — there are no card fields anywhere),
customer notes, internal admin notes and timestamps.

`public_token` is returned exactly once, at creation. Confirmation lookup is scoped by it,
so an order number alone never reveals an order.

**`order_items`** (10) — `order_id`, plus nullable `product_id` and `variant_id`. Product
name, SKU, variant description, unit price, quantity and line total are **copied** at
purchase time. Renaming or repricing a product never rewrites order history, and the
nullable foreign keys mean a deleted product does not destroy the record.

**`order_status_history`** (7) — `order_id`, `admin_user_id`, `old_status`, `new_status`,
an optional note and a timestamp. Every status change is attributable.

### Instance provenance

**`instance_metadata`** (10 columns) — a single row recording `instance_slug`,
`template_version` at initialization, `profile_schema_version`, `profile_hash`,
`enabled_features` (JSON), `initialized_at` and `last_bootstrap_at`. Written by
`commerce-instance apply` and reported by `commerce-instance manifest`.

This is **not** a tenancy mechanism: there is no `tenant_id`, and no other table
references it. One running application is still exactly one store.

### Media

**`media_assets`** (9) — `uploaded_by_id` → `admin_users.id`, stored filename, original
filename, URL, content type, byte size and timestamp. Files live on disk under a random
`uuid4().hex` name; the database holds metadata and a URL only. Nothing is ever stored as
Base64 or a BLOB.

## Database-level guarantees

Not left to application code:

- `package_items.package_product_id <> included_product_id`
- non-negative price, stock and order total
- positive quantity and discount
- unique slugs on products, categories, articles and static pages
- unique `order_number`, unique coupon `code`, unique admin `email`

## Migrations

Two revisions today. Adding a model means adding a migration:

```powershell
cd D:\Project\vista-store-e-commerce\backend
.venv\Scripts\alembic.exe revision --autogenerate -m "describe the change"
# read the generated file before trusting it
.venv\Scripts\alembic.exe upgrade head
```

Autogenerate does not reliably detect renames, check constraints, server defaults or type
changes. Review every generated revision by hand.

`tests/test_migrations.py` asserts that the migrated schema and `Base.metadata` contain
exactly the same tables, so a model that drifts from the migration fails the suite instead
of surfacing in production.
