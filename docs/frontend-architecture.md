# Frontend architecture

React 18 with Vite 6 and React Router, written in **JavaScript/JSX**. There is no
TypeScript here and none should be added: an earlier TypeScript migration was abandoned
and must not be reused.

One single-page application serves two independent areas — the public storefront and the
admin workspace — which share nothing but the HTTP client and the browser-storage helpers.

## Directory map

```
src/
  main.jsx            mounts <App/> inside <BrowserRouter>
  App.jsx             the route table, nothing else
  api/                client.js, publicApi.js, adminApi.js
  app/StoreProvider.jsx   shared storefront state
  styles/public/      the storefront design system, scoped to .vs-public
  components/public/  the storefront component library
    shell/            PublicShell, Header, Footer, MobileTabBar, Media, icons
    navigation/       CategoryMega, CategoryRail, MobileMenu
    overlays/         Overlay (Drawer/Modal), ShellOverlays, QuickView, Toast
    catalog/          ProductCard, PackageCard, CategoryCard, ProductGrid, FilterPanel
    home/             Hero, Banners, TrustStrip
    product/          Gallery, OptionPicker, ProductPanels
    cart/             CartDrawer, QuantityStepper, useCartLines
    search/           SearchBox, SearchOverlay
  components/         AddToCartButton, Maintenance, PreviewNotice (shared/standalone)
  hooks/              useStorefront, useCatalogQuery, useProductDetail,
                      useScrollLock, useFocusTrap, useMediaQuery, useCartCountPulse
  pages/              one route component per storefront route
  admin/              the admin workspace (own layout, own pages)
  services/           catalog.js, storefront.js, checkout.js — API to view-model
  storage/            safeStorage.js, cartStorage.js, authStorage.js
  utils/              productView.js, format.js, placeholder.js
  store.js            navigation structure and static copy only
  test/               Vitest suites and helpers
```

## Routing

`App.jsx` is only a route table. `/admin/*` renders `AdminApp`; every other path renders
`PublicShell` wrapped in `StoreProvider`.

Storefront routes:

```
/                       /shop                   /category/:slug
/offers                 /packages               /molds
/search?q=              /product/:slug          /cart
/checkout               /order-success/:orderNumber
/track-order            /blog                   /blog/:slug
/page/:slug             /about                  /privacy-policy
/return-policy          /terms                  /contact
/tools/calculator       *  → an intentional Not Found page
```

`/about`, `/privacy-policy`, `/return-policy` and `/terms` are direct links the original
storefront used; they resolve to the same `StaticPage` records as `/page/:slug`.

`/shop`, `/category/:slug`, `/offers`, `/packages`, `/molds` and `/search` are the same
`CatalogPage` under different `mode` props.

Because these are client-side routes, a production web server needs an SPA fallback or a
reload of `/product/x` returns 404. The Nginx template handles it with `try_files`.

## The storefront design system

All storefront styling lives in `src/styles/public/`, imported once from `main.jsx` and
scoped under **`.vs-public`**, the class on the storefront shell root. Tokens are named
(`--vs-container`, `--vs-section`, `--vs-primary`, `--vs-t-drawer`, `--vs-z-drawer`, …)
and defined only inside that scope.

That scoping is the rule to keep: `/admin` renders **outside** `.vs-public`, so no
storefront value can reach it. `src/index.css` holds only the document reset and the few
layout variables the admin workspace reads — storefront rules must not be added back
there. A test asserts that `--vs-primary` is unset on `/admin`.

Components take **props, not a view-model object**. Shared display shapes come from pure
helpers and small hooks:

- `utils/productView.js` — turns a normalized product into what a card, a quick view or a
  product page shows, including which of the three add-to-cart behaviours applies.
- `hooks/useStorefront.js` — `useMoney`, `useProductViews`, `useProductActions`,
  `useCategoryNav`.
- `hooks/useCatalogQuery.js` — catalogue filters, read from and written to the URL.

## State

`StoreProvider` holds what more than one storefront route needs: store settings,
categories, delivery areas, banners, the cart, the open overlay, search query and
suggestions, the applied coupon, the checkout form and recently-viewed products. Anything
used by a single route stays local to that route.

**Overlays are one value, not a set of booleans.** `overlay` is `null` or one of
`cart | menu | categories | search | filters | quick`. Opening one closes whatever was
open, so "only one drawer at a time" is a property of the state rather than a rule each
trigger has to remember.

Catalogue state (sort, price bound, on-sale, in-stock, category) lives in the URL, so a
filtered listing is shareable and the back button undoes a filter.

Persistent state goes through `src/storage/`:

| Helper | Stores | Where |
| --- | --- | --- |
| `cartStorage` | cart lines | `localStorage` |
| `authStorage` | admin token and profile | `localStorage` |
| — | `public_token` of a placed order | `sessionStorage` |

`safeStorage.js` wraps all of it, so a browser with storage disabled or full degrades
instead of throwing.

Because the order token lives in `sessionStorage`, `/track-order` works only in the
browser session that placed the order. That is intentional: the order number alone must
not reveal an order.

## API access

`src/api/client.js` is the single HTTP entry point. Auth headers, the error shape and the
401 recovery path exist in exactly one place.

- Base URL is `VITE_API_BASE_URL`, defaulting to `/api/v1` so the dev proxy handles
  same-origin requests with no configuration.
- `api.get/post/patch/delete` take `{ auth: true }` to attach the bearer token. Public
  calls never send it.
- Failures are normalised into an `ApiError` carrying `status`, `code` and `fields`, taken
  from the backend's `{"error": {...}}` body. UI code branches on `code`, not on prose.
- An unreachable server becomes `code: "network_error"` rather than a raw `TypeError`.
- A 401 triggers the registered unauthorized handler, which clears the stored session and
  returns the admin area to the login screen.

`publicApi.js` and `adminApi.js` are thin named wrappers over the endpoints. `services/`
turns API payloads into the shapes pages need — pricing text, badges, filter state — so
pages stay declarative.

## Storefront details

- **Overlays** share one implementation (`components/public/overlays/Overlay.jsx`):
  reference-counted scroll locking, a focus trap that restores focus to the opener,
  escape, scrim click and route change. Drawer sides are **physical** (`left` / `right`)
  on purpose — the layout is RTL throughout and the rule it depends on is visual:
  navigation from the right, the cart from the left. Logical properties invert exactly
  that.
- **`components/public/shell/Media.jsx`** is the only way an image is rendered. It always
  reserves its box with `aspect-ratio`, lazy-loads below-fold images, and falls back to a
  tone gradient (`utils/placeholder.js`) when a record has no artwork.
- **Store identity is data.** Name, tagline, contact details, social links, currency and
  brand colours come from `GET /store/settings`; the colours are applied as CSS custom
  properties. No client branding is hard-coded, and a field the owner has not filled in is
  omitted rather than shown as a placeholder.
- **`body` uses `overflow-x: clip`, never `hidden`** — `hidden` makes the body a scroll
  container, which silently disables every `position: sticky` inside it, the header
  included.
- **Home page composition is admin-controlled**: which sections appear, in what order,
  with which titles, comes from `home_sections`.
- **Every commercial number is server-supplied.** The checkout page displays only the
  figures returned by `POST /cart/price`; it never computes a total locally.
- **RTL**: `index.html` sets `lang="ar" dir="rtl"`, and layout uses logical properties
  (`inset-inline-start`, `margin-inline`) rather than left/right — except where the
  requirement is genuinely visual, which today means only the drawer sides above. Prices
  are `unicode-bidi: isolate` so a sale price and its struck original cannot interleave.

## Admin workspace

`/admin/*` renders `AdminApp`, which has its own layout and no storefront chrome.

```
/admin/login                     standalone, no navigation
/admin                           dashboard
/admin/products                  list, search, type and status filters, pagination
/admin/products/:productId       full editor
/admin/categories                /admin/orders            /admin/orders/:orderId
/admin/coupons                   /admin/delivery          /admin/hero
/admin/banners                   /admin/home              /admin/articles
/admin/pages                     /admin/media             /admin/settings
/admin/admins                    super admin only
/admin/audit                     super admin only
```

Unknown `/admin/*` paths redirect to the dashboard rather than showing the storefront's
Not Found page.

- A route wrapper redirects unauthenticated visitors to `/admin/login`, preserving the
  intended path.
- Super-admin-only entries are hidden from the navigation **and** guarded by a route
  wrapper — and the API enforces the same rule independently. The frontend guard is
  convenience, not security.
- `ResourceScreen.jsx` is a small declarative CRUD engine: most admin screens are a field
  list plus an API binding, which is why the workspace is broad without being large.
- `ui.jsx` holds the shared primitives (`DataTable`, `Badge`, form inputs).

## Tests

`src/test/` runs under jsdom with Vitest and Testing Library. `fetch` is stubbed per test
via `stubApi`, so nothing reaches a real server, and `setup.js` installs an in-memory
`Storage` polyfill because this jsdom build does not expose a resettable one.

`storefront.test.jsx` covers the shell, home sections, listing, product detail, the
intentional not-found pages, cart persistence, checkout validation, a successful checkout
and API-unreachable behaviour. `publicShell.test.jsx` covers landmarks, admin isolation,
the category panel, drawer exclusivity and scroll locking, focus restoration, search
suggestions, catalogue empty and error states and URL-carried sort. `productCards.test.jsx`
covers direct add, option-required add, sold-out, packages, sale pricing, quick view and
reduced motion. `admin.test.jsx` covers login, session restore and expiry, route guarding,
the product and order screens, super-admin navigation hiding, and the API client's token
and error handling.

Queries are scoped (`within`, `getByRole`) rather than global, because several Arabic
labels and money strings legitimately appear more than once on a page.

`setup.js` provides a controllable `matchMedia` (jsdom has none): it answers "no" to every
query by default, putting components on their desktop, full-motion path, and a test that
cares about a breakpoint replaces `window.__mediaMatches`.

Current: **84 passed**.
