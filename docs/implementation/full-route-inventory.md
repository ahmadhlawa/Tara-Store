# Full route inventory

Built from the router sources, not from memory:

- `frontend/src/App.jsx` — every public route
- `frontend/src/admin/AdminApp.jsx` — every admin route and its guard
- `backend/app/api/v1/router.py` and the generated OpenAPI document — every API operation

Counts at the time of the acceptance run (merge commit `f34ac40`):

| Surface | Count |
| --- | --- |
| Public SPA routes (including the 404 fallback) | 21 |
| Admin SPA routes (including the catch-all redirect) | 21 |
| API operations in `/api/v1/openapi.json` | 99 |

The browser suite walks all of them; see `full-admin-public-validation.md` for results.

Focused delta, 2026-08-07: coverage is local development validation with mock/demo data,
not per-control or production certification. The isolated media-root 404 is a fixture
configuration issue; see `full-admin-public-validation.md` for the current result.

## Public routes

All public routes render inside `PublicShell` with the storefront header, the category
rail and the footer. None of them require authentication, and none of them may render
admin chrome.

| Route | Component | Primary API calls | Main actions | Notes |
| --- | --- | --- | --- | --- |
| `/` | `HomePage` | `/hero-slides`, `/banners`, `/home-sections`, `/products/featured`, `/products/new`, `/products/bestsellers`, `/categories` | carousel prev/next, section CTAs, product cards, add to cart | Hero, banners and sections are all admin-controlled |
| `/shop` | `CatalogPage mode="shop"` | `/products` | filters, sort, pagination, add to cart | Full catalogue |
| `/category/:slug` | `CatalogPage mode="category"` | `/categories/{slug}`, `/products` | same as shop, scoped to the category | Inactive categories must 404 |
| `/offers` | `CatalogPage mode="offers"` | `/products` | add to cart | Discounted products only |
| `/packages` | `CatalogPage mode="packages"` | `/products/packages` | add to cart | `product_type=package` |
| `/molds` | `CatalogPage mode="molds"` | `/products/molds` | add to cart | `product_type=silicone_mold` |
| `/search` | `CatalogPage mode="search"` | `/products?q=` | search field, submit, empty state | Reads `?q=` |
| `/product/:slug` | `ProductDetailPage` | `/products/{slug}`, `/products/{slug}/related` | quantity, add to cart, gallery, specifications | Inactive products must 404 |
| `/cart` | `CartRoutePage` | `/cart/price` | quantity, remove, empty state, go to checkout | Server re-prices every line |
| `/checkout` | `CheckoutRoutePage` | `/cart/price`, `/coupons/validate`, `/delivery-areas`, `POST /orders` | full form, coupon, delivery zone, payment method, terms, submit | Order is persisted **before** the WhatsApp hand-off |
| `/order-success/:orderNumber` | `OrderSuccessRoutePage` | `/orders/{order_number}` | confirmation only | Reached only after a successful order |
| `/blog` | `BlogListPage` | `/articles` | article cards | Unpublished articles are excluded |
| `/blog/:slug` | `ArticleDetailPage` | `/articles/{slug}` | — | |
| `/page/:slug` | `StaticContentPage` | `/pages/{slug}` | — | Unpublished pages must 404 |
| `/about` | `StaticContentPage slug="about"` | `/pages/about` | — | Legacy direct link |
| `/privacy-policy` | `StaticContentPage` | `/pages/privacy-policy` | — | Legacy direct link |
| `/return-policy` | `StaticContentPage` | `/pages/return-policy` | — | Legacy direct link |
| `/terms` | `StaticContentPage` | `/pages/terms` | — | Legacy direct link |
| `/contact` | `ContactRoutePage` | `/store/settings` | WhatsApp, phone, map links | Driven by store settings |
| `/tools/calculator` | `CalculatorRoutePage` | — | numeric inputs | Client-side only |
| `*` | `NotFoundRoutePage` | — | back to home | Must keep storefront chrome |

There is deliberately **no public order-tracking route**. `TrackOrderPage.jsx` was
deleted on the feature branch and the header now exposes an admin-login icon in its
place (`Header.jsx`, `aria-label="تسجيل دخول الإدارة"`).

## Admin routes

`/admin/login` is standalone. Everything else is wrapped in `RequireAdmin`; the three
manager-only screens are additionally wrapped in `RequireSuperAdmin`, which redirects a
normal admin to `/admin`.

| Route | Component | Role | Primary API calls |
| --- | --- | --- | --- |
| `/admin/login` | `LoginPage` | anonymous | `POST /auth/login` |
| `/admin` | `DashboardPage` | admin | `/admin/dashboard` |
| `/admin/products` | `ProductsPage` | admin | `/admin/products` |
| `/admin/products/:productId` | `ProductEditorPage` | admin | `/admin/products/{id}` and its images, options, variants, specifications, package-items |
| `/admin/categories` | `CategoriesPage` | admin | `/admin/categories` |
| `/admin/orders` | `OrdersPage` | admin | `/admin/orders` |
| `/admin/orders/manual` | `ManualOrderPage` | **super_admin** | `POST /admin/orders/manual` |
| `/admin/orders/:orderId` | `OrderDetailPage` | admin | `/admin/orders/{id}`, `/status`, `/complete`, `/reopen`, `/notes`, `/invoice` |
| `/admin/invoices` | `InvoicesPage` | admin | `/admin/invoices` |
| `/admin/invoices/:invoiceNumber` | `InvoiceDetailPage` | admin | `/admin/invoices/{number}`, `/payment`, `/cancel` |
| `/admin/coupons` | `CouponsPage` | admin | `/admin/coupons` |
| `/admin/delivery` | `DeliveryAreasPage` | admin | `/admin/delivery-areas` |
| `/admin/hero` | `HeroSlidesPage` | admin | `/admin/hero-slides` |
| `/admin/banners` | `BannersPage` | admin | `/admin/banners` |
| `/admin/home` | `HomeSectionsPage` | admin | `/admin/home-sections` |
| `/admin/articles` | `ArticlesPage` | admin | `/admin/articles` |
| `/admin/pages` | `StaticPagesPage` | admin | `/admin/pages` |
| `/admin/media` | `MediaPage` | admin | `/admin/media` |
| `/admin/settings` | `SettingsPage` | admin | `/admin/settings` |
| `/admin/admins` | `AdminsPage` | **super_admin** | `/admin/admins` |
| `/admin/audit` | `AuditLogPage` | **super_admin** | `/admin/audit-logs` |
| `/admin/*` | redirect | admin | — |

## Expected states

Every list screen has four states the suite treats as first class:

- **loading** — a spinner that must clear; a permanently spinning screen is a failure.
- **empty** — an Arabic empty message, never a blank panel and never a raw `[]`.
- **error** — an Arabic message. A raw English backend detail reaching an Arabic screen
  is a defect.
- **success** — rows rendered with localized labels, never raw enum values.
