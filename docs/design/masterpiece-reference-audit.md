# Masterpiece reference audit

Clean-room observation of `masterpiece.ps` (home + `/product-category/packaging-solutions/`),
measured in headless Chrome at 1920 / 1440 / 768 / 390 CSS px on 2026-08-02.
Nothing below is copied source: these are rendered measurements and behavioural
notes used to calibrate the Vista rebuild.

## What should be adapted

* **A three-band header.** A slim full-width utility strip, then a tall white
  identity band (logo on the RTL right, one wide search field in the middle,
  a help/contact block on the left), then a coloured navigation band carrying a
  prominent "all categories" trigger, the main links, and the cart.
* **A dedicated category trigger** that is visually the heaviest item in the nav
  band — it reads as the primary way into the catalogue, not as an afterthought.
* **Catalogue density.** Four real columns on desktop with a *small* gap; the
  page reads as a shop, not as four posters.
* **Image-first product cards** with a square image, a short two-line title, a
  clear price and one full-width action button pinned at the bottom.
* **A catalogue toolbar** that carries result count, sort, and grid density in a
  single calm row above the grid, with subcategory links reachable from the
  category header.
* **An image-led category header** — a wide banner with the category name over
  the artwork and its children listed under it.
* **A mobile bottom action bar** (home / cart / menu / filter) so the primary
  catalogue verbs stay reachable with a thumb.
* **Restrained motion.** Every measured transition is 0.2–0.4 s; nothing
  bounces, nothing loops.

## What should not be copied

* The brand palette (`#4A575E` slate, `#D9C49E` sand), the Masterpiece logo, the
  wordmark, and the leaf mark.
* Product photography, banner artwork, category imagery and the icon rail glyphs.
* Any WooCommerce/Elementor markup, class names, CSS or JavaScript.
* Product data, prices, SKUs, copy, policy text and contact details.
* The fixed right-hand icon rail — it is dense, unlabelled and largely
  decorative; Vista gets a labelled category drawer instead.
* The 78 px outlined hero headline over a photograph: the contrast is poor and
  the wordmark is illegible at 390 px.

## Measured design tokens

| Token | 1920 | 1440 | 768 | 390 |
| --- | --- | --- | --- | --- |
| Content width | 1370 | 1350 | 738 | 360 |
| Side gutter | 15 | 15 | 15 | 15 |
| Header height (sticky part) | 140 | 140 | 120 | 120 |
| Utility strip | 40 | 40 | 40 | 40 |
| Product columns | 4 | 4 | 2 | 2 |
| Product column width | 327.5 | 322.5 | 364 | 175 |
| Grid gap | 20 | 20 | 10 | 10 |
| Card height | 452 | 447 | 516 | 329 |

Other measured values:

* Product image aspect ratio **1:1** (`1019 × 1024` source, rendered square).
* Card: no border, no shadow, no radius on the tile itself; separation comes
  from whitespace. The action button is `36 px` tall, `5 px` radius,
  `13 px / 600`, inset `35 px` from each card edge on desktop.
* Price `15 px / 400`; body `Cairo 15 px / 24 px`, text `#777`, headings `#333`.
* `h1` **78 px** over the category banner, **36 px** at ≤768; section `h2`
  **24 px / 500**.
* Dominant transition durations: `0.25 s` and `0.3 s`; a couple of long
  `0.4–0.5 s` entrance eases. No spring, no bounce.
* Page background pure white; the only large tinted surfaces are photographs.

## Desktop behaviour

* The header is **not** sticky on the reference — it scrolls away. The category
  trigger and cart therefore disappear, which is the main usability weakness.
* Category trigger opens a panel listing top-level categories; hovering a nav
  item with children opens a dropdown, ~0.25 s fade.
* Product hover: the tile lifts the image slightly and swaps in the second
  gallery image where one exists; the action button gains a darker fill. No
  layout shift, no card-level translate.
* Grid density control re-renders the same grid at 9 / 12 / 18 / 24 items; the
  three icon buttons switch between list, 3-up and 4-up.
* Sort is a plain `select` styled as a pill.
* The cart shows running total plus a badge; adding an item updates the badge
  in place.

## Mobile behaviour

* Header collapses to 60 px: account icon on the left, centred logo, a labelled
  menu button on the right. The search field moves to its own 60 px row below,
  full-width, pill-shaped.
* Category banner shortens to ~110 px and the title shrinks to 36 px.
* The toolbar becomes two controls: "show options" (filters) and a sort icon.
* Grid is 2 columns at both 390 and 768 with a 10 px gap — the cards get
  genuinely narrow (175 px) and the title/price/SKU/button stack stays legible
  only because the type is small.
* A fixed four-slot bottom bar hosts home, cart (with badge), menu and filter.
* No hover-dependent affordance survives: the action button is always visible.

## Interaction model

1. Catalogue entry is via the category trigger or the banner subcategory links.
2. Listing → toolbar (count, density, sort) → grid → paginated tail.
3. A product that needs options never adds directly; the card button reads
   "choose an option" and routes to the product page.
4. Cart is a header affordance with a live badge and total.
5. Overlays close on overlay click; escape handling is inconsistent.

## Vista-specific adaptations

* **Keep the Vista palette.** Teal `#1F4E4A`, gold `#C9A24B`, green `#2E7D5B`
  on the warm `#FBF9F6` page — driven by `StoreSettings`, so a client instance
  restyles itself. Nothing from the reference palette is carried over.
* **Make the header sticky and compact.** The reference's biggest flaw is losing
  the cart and category trigger on scroll. Vista keeps a 124 px header that
  compresses to the 56 px nav band once the page scrolls past 40 px.
* **Widen the gutters slightly** (20 px desktop, 16 px mobile) and cap the
  container at 1400 px so 1920 does not read as an empty stage.
* **Keep 4 columns but raise the gap to 20 px and add a 3-column tier** between
  900 and 1279 px, so cards never fall below ~250 px on desktop.
* **Give cards a light surface, a 16 px radius and a hairline border.** The
  reference's borderless tiles work on pure white; on Vista's warm page they
  need a surface to sit on.
* **Replace the icon rail with a labelled category drawer** opening from the RTL
  right, and a horizontal category rail under the header on desktop.
* **Add Quick View and a cart drawer**, which the reference does not have — both
  are required by the brief and both reduce navigation cost on a catalogue this
  dense.
* **Cart drawer opens from the left** so it cannot collide with the category and
  menu drawers, which open from the right in RTL.
* **Category headers use the real category image** with a legible scrim and a
  32–44 px title rather than 78 px outlined text.
* **Mobile keeps the bottom action bar** but with four labelled targets ≥44 px
  and no hidden hover behaviour.
* **Motion is codified**: 140 ms state, 200 ms controls, 260 ms cards/overlays,
  300 ms drawers, 600 ms hero, all on `cubic-bezier(.22,1,.36,1)`, all disabled
  under `prefers-reduced-motion`.
* **Filters map to real API fields only** (`category`, `on_sale`, `in_stock`,
  `min_price`, `max_price`, `sort`) — no decorative filter that the backend
  cannot honour.
