# API modules

**62 paths.** Everything is under `/api/v1` except `/health`. Interactive documentation is
served at `/api/v1/docs`, and the schema at `/api/v1/openapi.json`.

## Conventions

**Errors** — one shape everywhere:

```json
{ "error": { "code": "coupon_expired", "message": "انتهت صلاحية الكود." } }
```

Validation failures use HTTP 422, code `validation_error`, and add
`fields: [{ "field": "...", "message": "..." }]`. Branch on `code`, never on the message.

**Pagination** — list endpoints take `page` and `page_size` and return:

```json
{ "items": [...], "total": 120, "page": 1, "page_size": 20, "pages": 6 }
```

**Authentication** — `/api/v1/admin/*` and `/auth/me` require `Authorization: Bearer <token>`.
Public endpoints must never be sent one.

**Money** — decimal numbers in JSON, computed server-side. No endpoint accepts a
client-supplied price, discount or total.

---

## Meta

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Outside the API prefix. `{"status":"ok","app":...,"environment":...}` |

## Auth — `endpoints/auth.py`

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/login` | `{email, password}` → `{access_token, token_type, expires_in_minutes}`. One generic failure response, so it does not reveal whether an address exists |
| GET | `/auth/me` | The signed-in administrator. Re-reads the account, so a deactivated admin's token stops working at once |

## Public catalog — `endpoints/public_catalog.py`

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/categories` | Active categories |
| GET | `/categories/{slug}` | One category |
| GET | `/products` | The main listing — see filters below |
| GET | `/products/featured` | |
| GET | `/products/new` | |
| GET | `/products/bestsellers` | |
| GET | `/products/packages` | `product_type = package` |
| GET | `/products/molds` | `product_type = mold` |
| GET | `/products/{slug}` | Full detail: images, specifications, options, variants, package contents |
| GET | `/products/{slug}/related` | Same category, excluding the product itself |

`/products` accepts `q`, `category`, `product_type`, `is_featured`, `is_new`,
`is_bestseller`, `on_sale`, `in_stock`, `min_price`, `max_price`, `sort`, `page`,
`page_size`. `q` matches the normalised `search_text` column, so it tolerates spelling and
diacritic variation. Inactive products are never returned.

## Public content — `endpoints/public_content.py`

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/store/settings` | Store identity, contact, colours, currency. Excludes `id` and `order_notifications_email` |
| GET | `/hero-slides` | Active, within their schedule window |
| GET | `/banners` | Active, within their schedule window |
| GET | `/home-sections` | Visible sections in order — decides what the home page contains |
| GET | `/delivery-areas` | Active areas with fees and thresholds |
| GET | `/articles` | Published only, paginated |
| GET | `/articles/{slug}` | |
| GET | `/pages/{slug}` | Published static page |

## Public checkout — `endpoints/public_checkout.py`

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/coupons/validate` | `{code, subtotal}` → validity and the computed discount |
| POST | `/cart/price` | **The authoritative pricing call.** Takes product ids and quantities only, returns priced lines, subtotal, discount, delivery fee and total |
| POST | `/orders` | Guest checkout. Re-prices everything server-side, decrements stock and returns `public_token` **once** |
| GET | `/orders/{order_number}?token=` | Confirmation lookup; the token is required |

There is no field on any of these in which a client could submit a price.

## Admin catalog — `endpoints/admin_catalog.py`

| Method | Path |
| --- | --- |
| GET, POST | `/admin/categories` |
| PATCH, DELETE | `/admin/categories/{category_id}` |
| GET, POST | `/admin/products` |
| GET, PATCH, DELETE | `/admin/products/{product_id}` |
| GET, POST | `/admin/products/{product_id}/images` |
| DELETE | `/admin/products/{product_id}/images/{image_id}` |
| PUT | `/admin/products/{product_id}/specifications` (replaces the whole list) |
| GET, PUT | `/admin/products/{product_id}/options` (replaces the whole set) |
| GET, POST | `/admin/products/{product_id}/variants` |
| PATCH, DELETE | `/admin/products/{product_id}/variants/{variant_id}` |
| GET, POST | `/admin/products/{product_id}/package-items` |
| DELETE | `/admin/products/{product_id}/package-items/{item_id}` |

The admin listing shows inactive products too, which is the point of the status filter.

## Admin commerce — `endpoints/admin_commerce.py`

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/admin/dashboard` | Counts, revenue, low stock, recent orders |
| GET, POST | `/admin/coupons` | |
| PATCH, DELETE | `/admin/coupons/{coupon_id}` | |
| GET, POST | `/admin/delivery-areas` | |
| PATCH, DELETE | `/admin/delivery-areas/{area_id}` | |
| GET | `/admin/orders` | Search and status filter, paginated |
| GET | `/admin/orders/{order_id}` | Items, totals and status history |
| POST | `/admin/orders/{order_id}/status` | `{status, note}`. Writes history with the acting admin; cancelling restores stock exactly once |
| PATCH | `/admin/orders/{order_id}/notes` | Internal notes, never shown to the customer |

Orders cannot be created or deleted through the admin API. They arrive from checkout and
are then only advanced through statuses.

## Admin content — `endpoints/admin_content.py`

| Method | Path |
| --- | --- |
| GET, PATCH | `/admin/settings` |
| GET, POST | `/admin/hero-slides` · PATCH, DELETE `/admin/hero-slides/{slide_id}` |
| GET, POST | `/admin/banners` · PATCH, DELETE `/admin/banners/{banner_id}` |
| GET, POST | `/admin/home-sections` · PATCH, DELETE `/admin/home-sections/{section_id}` |
| GET, POST | `/admin/articles` · PATCH, DELETE `/admin/articles/{article_id}` |
| GET, POST | `/admin/pages` · PATCH, DELETE `/admin/pages/{page_id}` |

## Admin media — `endpoints/admin_media.py`

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/admin/media` | Paginated library |
| POST | `/admin/media` | `multipart/form-data`. Validated by magic bytes (JPEG, PNG, WebP, GIF, ICO) and size-limited by `MAX_UPLOAD_SIZE_BYTES`; stored under a random name |
| DELETE | `/admin/media/{asset_id}` | Removes the row and the file |

Deleting an asset does not rewrite products that already reference its URL; they fall back
to the design's gradient placeholder.

## Admin users — `endpoints/admin_users.py` (super admin only)

| Method | Path | Notes |
| --- | --- | --- |
| GET, POST | `/admin/admins` | |
| PATCH, DELETE | `/admin/admins/{admin_id}` | A super admin cannot disable, demote or delete itself, and the last active super admin cannot be deleted |
| GET | `/admin/audit-logs` | Paginated, newest first |

An `admin` who calls these gets 403 from the API regardless of what the frontend shows.
