# Storefront rebuild — browser visual QA

Chrome 1440 / 768 / 390 (plus 1920 for whitespace), driven over the DevTools
Protocol against the Vista preview database (`backend/data/vista_preview.db`:
8 categories, 35 products, 5 packages, 4 hero slides, 3 banners, 7 home
sections). Screenshots are working artefacts under the session scratchpad
`…/641636a7-…/scratchpad/` and are not committed; paths below name the file.

Every viewport on every route below reported `document.scrollWidth - innerWidth
= 0` and no element wider than the viewport.

## Routes

| Route | Viewport | Result | Screenshot |
| --- | --- | --- | --- |
| `/` | 1440 / 768 / 390 | Pass — hero + promo column, category grid, featured/new grids, bestseller rail, package grid, promo strip, editorial split, trust strip | `shots3/home-*` |
| `/shop` | 1440 / 768 / 390 | Pass — plain header, sidebar filters ≥1024, toolbar, 4/3/2 columns | `shots3/shop-*` |
| `/category/wedding-invitations` | 1440 / 768 / 390 | Pass — image-led category header, breadcrumb over the scrim | `shots3/category-*` |
| `/offers` | 1440 / 768 / 390 | Pass — 9 results, sale badges, mixed product and package cards | `shots2/offers-*` |
| `/packages` | 1440 / 768 / 390 | Pass — package cards with cover, count and own action | `shots2/packages-*` |
| `/search?q=كرت` | 1440 / 768 / 390 | Pass — term echoed in the heading, results listed | `shots2/search-q-*` |
| `/search` (no term) | 1440 | Pass — asks for a term, makes no request | fixed during QA |
| `/product/preview-wedding-card-classic` | 1440 / 768 / 390 | Pass — gallery, price, stock, buy row, panels beside the gallery, related | `shots4/product-preview-wedding-card-classic-*` |
| `/product/preview-package-graduation` | 1440 / 768 / 390 | Pass — package badge, contents list, package pricing | `shots4/product-preview-package-graduation-*` |
| `/cart` (empty) | 1440 / 768 / 390 | Pass — intentional empty state | `shots2/cart-*` |
| `/checkout` | 1440 | Pass — COD + manual only, no card field, server totals | `shotsC/checkout-*` |
| `/order-success/ORD-260802-9132` | 1440 | Pass — order number, summary, payment method, next steps | `shotsC/order-success.png` |
| `/blog` | 1440 / 768 / 390 | Pass — intentional "no articles yet" state (preview data has none) | `shots2/blog-*` |
| `/page/about` | 1440 / 768 / 390 | Pass — published static page | `shots2/page-about-*` |
| `/contact` | 1440 / 768 / 390 | Pass — form plus a contact panel that omits the fields the owner has not set | `shots2/contact-*` |
| `/no-such-page` | 1440 / 768 / 390 | Pass — 404 with two ways back | `shots2/no-such-page-*` |
| Maintenance mode | 1440 / 768 / 390 | Pass — replaces every public route in place, no redirect; setting restored to off afterwards | `shots5/*` |
| `/admin` | 1440 | Pass — no `.vs-public`, no storefront header or footer, `--vs-primary` unset | `shotsC/admin.png` |

## Interactions

All checks below were asserted programmatically in the browser
(`scratchpad/interact.mjs`, `checkout.mjs`) rather than read off a screenshot.

| Check | Result |
| --- | --- |
| Header stays pinned while scrolling | Pass (after the fix below) |
| Category panel opens, dims the page under the header, locks scroll | Pass |
| Escape closes the category panel and unlocks scroll | Pass |
| Quick view opens as a labelled modal with real detail data | Pass |
| Adding from quick view opens the cart drawer | Pass (after fix) |
| Cart drawer opens from the visual left | Pass (after fix) |
| Quantity control updates the line; remove empties the drawer | Pass |
| Escape closes the drawer and focus returns to the trigger | Pass |
| Only one overlay open at a time (menu → cart → search) | Pass |
| Mobile menu, search sheet and tab bar | Pass |
| Header search returns live suggestions | Pass |
| Product page add opens the cart drawer | Pass |
| Package page shows its contents | Pass |
| Checkout: empty submit reports five field errors tied to their inputs | Pass |
| Checkout: creates order `ORD-260802-9132` and empties the cart | Pass |
| 1920: container capped at 1400, gutters 260, cards 254–325px | Pass |

## Responsive sweep

Measured at every width the brief names, on `/shop` and `/`:

| Width | Product columns | Card width | Tab bar | Overflow |
| --- | --- | --- | --- | --- |
| 360 | 2 | 158 | yes | 0 |
| 390 | 2 | 173 | yes | 0 |
| 430 | 2 | 193 | yes | 0 |
| 768 | 3 | 235 | yes | 0 |
| 1024 | 3 | 221 / 316 | no | 0 |
| 1280 | 4 | 224 / 295 | no | 0 |
| 1440 | 4 | 254 / 325 | no | 0 |
| 1920 | 4 | 254 / 325 | no | 0 |

(Two card widths where the catalogue has a filter sidebar and the homepage does
not.) The tablet tier was corrected during this sweep: 768 was falling to two
columns with oversized cards, and now holds three down to 700px.

## Defects found and fixed

1. **Sticky was disabled site-wide.** `html, body { overflow-x: hidden }` (carried
   over from the old stylesheet) made the body a scroll container, which
   silently disables `position: sticky` for everything inside it. The header
   scrolled away (`headerTop: -865` at `scrollY: 900`) and both sticky
   sidebars were inert. Changed to `overflow-x: clip`, which keeps the overflow
   guard without creating a scroll container. Header now pins at `0`, the order
   summary at `144`.
2. **Drawers opened on the wrong sides.** In RTL `inset-inline-start` is the
   *right* edge, so the cart arrived from the right and the navigation from the
   left — the opposite of the design — and the slide animations pulled against
   the placement. Drawer sides are now physical (`left` / `right`) with the
   reason recorded in the stylesheet.
3. **Add-to-cart claimed success when it had refused.** Clicking "add" in the
   quick view without choosing an option showed the error *and* flipped the
   button to "تمت الإضافة". `onAdd` may now return `false`; the quick view and
   the product page use it.
4. **Adding from quick view left an empty screen.** The shared 620 ms reveal
   delay ran after the modal had already closed. The quick view now opens the
   cart immediately, since it has already acknowledged the action itself.
5. **`/search` with no term listed the whole catalogue** under "search results".
   It now shows a prompt and makes no request.
6. **Dead column on the product page.** A square gallery outran a short
   information column, leaving ~340 px of blank page beside it. The gallery is
   capped at 540 px and the description/specification panels moved into the
   grid's second column, filling the space.
7. **Checkout errors lingered after being fixed.** Field messages stayed until
   the next submit; validation now re-runs on change once errors are showing.
8. **Prices could interleave.** A sale price and its struck original are now
   separate bidi runs (`unicode-bidi: isolate`).
9. **React warning on every image** (`fetchPriority` unknown prop) — removed;
   `loading` already carries the intent.

QA-harness defects (not product code): two concurrent headless runs shared one
debug port and hung; the driver now takes a random port.

## Remaining limitations

* **Preview artwork is abstract.** The preview dataset generates its own
  gradient PNGs — the template ships no binary assets — so every product,
  category and banner image is a tone gradient. The layout was designed and
  judged against that; with real photography the same grids will read
  considerably richer. Not a frontend defect and deliberately not "fixed" by
  editing seed data.
* **No variant product in the preview data** (`product_options` and
  `product_variants` are both empty). The option-required path — card label
  "اختر الخيارات", quick-view picker, refusal to add without a choice, variant
  pricing — is covered by frontend tests against fixtures and by a backend test
  for `has_options`, but was not exercised against the preview database in the
  browser.
* **No published articles**, so `/blog` was verified only in its empty state.
* **StoreSettings has no phone, WhatsApp, address, hours, tagline, logo or
  announcement.** The header contact block, the announcement strip, the floating
  WhatsApp button and most of the footer contact column therefore did not render
  during QA; each is conditional and was verified in the test suite instead.
* Screenshots were taken in headless Chrome with a device-pixel ratio of 1; no
  physical device testing was performed.
