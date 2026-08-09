# Admin capabilities

What an administrator can actually do, screen by screen. Everything listed here is
implemented and reachable at `/admin`; nothing below is aspirational.

Sign in at `/admin/login`. There is no self-registration and no password reset by email —
accounts are created by another administrator or from the command line.

## Roles

| Role | Can do |
| --- | --- |
| `admin` | Everything below except admin accounts and the audit log |
| `super_admin` | All of it, including `/admin/admins` and `/admin/audit` |

Super-admin-only entries are hidden from the navigation, guarded by a route wrapper, and
enforced independently by the API. The API is the real boundary.

## Dashboard — `/admin`

Product totals and how many are active, category count, published articles, active
coupons, total and pending orders, orders broken down by status, total revenue, a
low-stock count, and recent orders. Read-only.

## Products — `/admin/products`

List with text search, product-type filter, status filter and pagination. Inactive
products appear here, which is the point of the status filter.

`/admin/products/:productId` edits everything about one product:

- **Core** — name, slug, SKU, short description, full description, category, product type
  (standard / package / mold)
- **Pricing** — price, `compare_at_price` (display-only reference, never charged), cost
  price
- **Inventory** — stock quantity, `track_inventory`, low-stock threshold
- **Flags** — active, featured, new, bestseller, sort order
- **SEO** — title and description
- **Images** — attach from the media library, reorder, set the primary image, remove
- **Specifications** — ordered label/value pairs, replaced as a set
- **Options and variants** — define options (e.g. size, colour) and their values, then
  create variants with their own SKU, price and stock. A selected variant's stock and
  price take precedence over the product's
- **Package contents** — for package products only: which products are included, in what
  quantity, with an optional display note. A package cannot contain itself

## Categories — `/admin/categories`

Create, edit, delete. Categories nest through a parent reference. Slugs are generated and
kept unique.

## Orders — `/admin/orders`

List with search and status filter. `/admin/orders/:orderId` shows the full order:
customer details, delivery area, immutable line items, the server-computed totals, and the
status history.

An administrator can:

- **Change the status**, with an optional note. Every change is recorded in the history
  with the acting administrator and a timestamp
- **Cancel**, after a confirmation step. Cancelling restores stock exactly once; a
  cancelled order cannot re-enter a stock-holding status
- **Add internal notes**, never shown to the customer

Orders cannot be created or deleted from the admin area. They arrive from checkout and are
only ever advanced through statuses. Line items are snapshots — editing a product later
never rewrites an existing order.

## Coupons — `/admin/coupons`

Create, edit, delete. Percentage or fixed discount, minimum order, maximum discount cap,
usage limit, validity window, active flag. Every rule is re-checked server-side at
pricing and at checkout; the discount can never exceed the subtotal. The usage counter
increments in the same transaction as the order.

## Delivery areas — `/admin/delivery`

Create, edit, delete. Name, delivery fee, optional minimum order, optional free-delivery
threshold, active flag. Inactive areas are rejected at checkout and hidden from the
storefront's area selector.

## Home page composition

Three screens decide what the home page shows:

- **`/admin/hero`** — hero slides: image, title, subtitle, description, button label and
  URL, order, and an optional schedule window
- **`/admin/banners`** — promotional banners with placement, order and schedule
- **`/admin/home`** — the sections themselves: which appear, in what order, with which
  titles and descriptions

A section hidden here disappears from the storefront without a deployment.

## Content

- **`/admin/articles`** — blog posts: title, slug, excerpt, body, cover image, publication
  state, SEO fields. Unpublished posts are invisible publicly
- **`/admin/pages`** — static pages behind `/page/:slug`, including the About, Privacy
  Policy, Return Policy and Terms pages the storefront links to directly

## Media — `/admin/media`

Upload images, copy a URL, delete. Uploads are validated by magic bytes (JPEG, PNG, WebP,
GIF, ICO) rather than by filename, and are size-limited. Files are stored under a random
name; the database keeps metadata and a URL.

Deleting an asset does not rewrite products that reference its URL — those fall back to
the design's gradient placeholder.

## Settings — `/admin/settings`

The store's identity, all of it data rather than code:

- Name, tagline, logo, favicon
- Phone, WhatsApp, email, address, working hours
- Social links
- Brand colours, applied to the storefront as CSS custom properties
- Currency
- Default SEO title and description
- Order notification address (never exposed on the public settings endpoint)
- `maintenance_mode` — turning it on closes the public storefront: the shop shows an
  Arabic maintenance screen built from this store's identity and contact details, and the
  public catalog, checkout and editorial endpoints answer `503 maintenance_mode`. Admin
  login, the admin API and `/health` stay open, so the owner can switch it back off from
  this same screen; the storefront returns on the next request, with no rebuild or restart

## Admin accounts — `/admin/admins` (super admin only)

Create, edit, deactivate and delete administrators, and set roles. Guardrails enforced by
the API:

- A super admin cannot disable, demote or delete itself
- The last active super admin cannot be deleted
- Deactivating an account invalidates its existing token on the next request

## Audit log — `/admin/audit` (super admin only)

Paginated, newest first. Records product, category, order, coupon, settings, media and
admin changes, plus logins, each with the acting administrator, the affected entity and a
metadata blob. Credentials and tokens are stripped before anything is written.
