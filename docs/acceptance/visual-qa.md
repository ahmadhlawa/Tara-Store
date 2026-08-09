# Visual acceptance — Golden Template 0.3.0-rc.1

**Performed in a real browser.** Chrome 151 (Blink), headless, driven over the DevTools
Protocol by a throwaway operator script. Nothing was installed to do this: the browser was
already on the machine and Node 25 ships a global `WebSocket`, so no browser-testing stack
(Playwright, Puppeteer, Selenium) was added to the repository or to `package.json`.

**What was inspected:** a real client instance created from a profile in this session — a
temporary SQLite database, a temporary uploads directory, one category, one standard
product with two specifications and one uploaded image, one package, one silicone mould,
one article, one coupon, one hero slide, one delivery area and one guest order. Not the
demo seed.

Each route was loaded at **390 px**, **768 px** and **1440 px** and, at every width,
machine-checked for horizontal overflow past the viewport, overlapping text boxes, an empty
render, broken images and console errors, then captured as a full-page screenshot and read.

**Result: 23 routes × 3 viewports = 69 passes, plus 3 maintenance routes × 3 viewports = 9.
Two real layout defects were found and fixed; both are re-verified below.**

---

## 1. Public routes

| Route | Path | 390 | 768 | 1440 | Notes |
| --- | --- | :-: | :-: | :-: | --- |
| Home | `/` | ✅ | ✅ | ✅ | hero slide, categories, featured/new/bestseller rows, trust strip |
| Shop / listing | `/shop` | ✅ | ✅ | ✅ | filter sidebar on desktop, filter button on mobile |
| Category | `/category/ريزن` | ✅ | ✅ | ✅ | breadcrumb and heading from the category |
| Product detail | `/product/ريزن-شفاف-عالي-الجودة` | ✅ | ✅ | ✅ | uploaded image renders; price 150 ₪, `compare_at` 200 ₪ struck through; specification tab |
| Packages | `/packages` | ✅ | ✅ | ✅ | |
| Silicone moulds | `/molds` | ✅ | ✅ | ✅ | |
| Cart | `/cart` | ✅ | ✅ | ✅ | **defect found and fixed — see §3.1** |
| Checkout | `/checkout` | ✅ | ✅ | ✅ | full form, validation messages, area select, terms checkbox |
| Order success | `/order-success/ORD-…` | ✅ | ✅ | ✅ | token-scoped lookup from `sessionStorage` |
| Blog | `/blog` | ✅ | ✅ | ✅ | |
| Article | `/blog/كيف-تبدأ-مع-الريزن` | ✅ | ✅ | ✅ | |
| Static page | `/page/about` | ✅ | ✅ | ✅ | page created empty by bootstrap; renders its intentional lead |
| Not Found | `/no-such-page` | ✅ | ✅ | ✅ | intentional 404 screen, not a blank route |
| Maintenance | `/`, `/shop` with the setting on | ✅ | ✅ | ✅ | see §2 |

## 2. Maintenance screen

Captured with `maintenance_mode` genuinely on, over real HTTP.

| Check | Result |
| --- | --- |
| Public routes replaced by the maintenance screen | ✅ every public path, including `/` and deep links |
| Arabic RTL | ✅ `dir="rtl"`, right-aligned, Arabic copy |
| Store identity | ✅ store name and tagline from the client profile |
| Safe contact information | ✅ WhatsApp, phone, email, working hours — nothing else |
| Private settings exposed | ✅ none; the screen reads only the public settings projection |
| Redirect loop | ✅ none — the screen replaces the layout in place, no navigation happens |
| Admin login reachable | ✅ `/admin/login` renders normally at all three widths |
| Storefront restored on disable | ✅ next request served again; no rebuild, no restart |
| Overflow / overlap / console errors | ✅ zero at 390, 768 and 1440 |

## 3. Defects found and fixed

### 3.1 The cart's order summary was placed in an off-canvas column

`CartPage` pinned its two children with `grid-column:1` and `grid-column:2` against
`grid-template-columns: var(--shop)`. Below 900 px `--shop` collapses to a single `1fr`
column, so `grid-column:2` created an **implicit** second column which, in RTL, sat off the
left edge — 118 px of the summary card, including most of the "إتمام الطلب" button, was
clipped by the global `overflow-x:hidden` and simply unreachable on a phone.

The same declarations also inverted the desktop layout: the summary occupied the wide
`1fr` column and the item list was squeezed into the 250 px one.

Fixed by removing both `grid-column` declarations and letting auto-placement plus the
existing `order` do the work — the pattern the listing page already uses. Desktop now shows
the summary as a 250 px sidebar beside a wide item list; mobile stacks cleanly with no
clipping.

### 3.2 A long store name pushed the cart button off the mobile header

The header's logo block was `flex:0 0 auto`, so it could not shrink. The store name is
client data, and a realistic one ("متجر القبول — المالك") pushed the whole action group
7 px past the edge at 390 px, clipping the cart button and its badge on **every** public
route.

Fixed with `flex:0 1 auto; min-width:0` on the logo block and ellipsis truncation on the
name and tagline. Nothing shrinks while there is room, so wider layouts are unchanged.

### 3.3 The shipped `index.html` carried a previous client's identity

`<title>تست — مستلزمات الريزن والشموع الحرفية</title>` and a "T" monogram favicon were
baked into the template. The storefront overwrites the title from `StoreSettings.seo_title`,
but the admin workspace never did — so every client's admin tab read another store's name.

Fixed: a neutral title and a neutral bag mark in `index.html`, and `AdminLayout` now sets
its own document title.

## 4. Admin routes

Inspected signed in as a real `super_admin` whose token was issued by the live API.

| Route | Path | 390 | 768 | 1440 | Notes |
| --- | --- | :-: | :-: | :-: | --- |
| Login | `/admin/login` | ✅ | ✅ | ✅ | no storefront chrome |
| Dashboard | `/admin` | ✅ | ✅ | ✅ | counters and recent orders |
| Products | `/admin/products` | ✅ | ✅ | ✅ | table scrolls inside its own container on mobile |
| Product editor | `/admin/products/1` | ✅ | ✅ | ✅ | tabs, specification rows, image panel |
| Categories | `/admin/categories` | ✅ | ✅ | ✅ | |
| Orders | `/admin/orders` | ✅ | ✅ | ✅ | search field and status filter |
| Order detail | `/admin/orders/1` | ✅ | ✅ | ✅ | items table and status-history table |
| Home content | `/admin/home` | ✅ | ✅ | ✅ | the seven sections bootstrap created |
| Media | `/admin/media` | ✅ | ✅ | ✅ | the uploaded asset is listed and its thumbnail loads |
| Settings | `/admin/settings` | ✅ | ✅ | ✅ | owner-edited values, maintenance-mode toggle |

## 5. Cross-cutting checks

| Check | Result |
| --- | --- |
| Arabic RTL | ✅ `dir="rtl"` resolved on every route, public and admin |
| Horizontal overflow | ✅ 0 px past the viewport on all 78 route × viewport combinations, after the §3 fixes |
| Text overlap | ✅ no intersecting leaf text boxes on any route or width |
| Navigation | ✅ desktop nav bar and mega menu; mobile drawer button; category chip row |
| Forms and validation | ✅ driven in the browser — see §5.1 |
| Dialogs and overlays | ✅ driven in the browser — see §5.1 |
| Tables on mobile | ✅ every admin table sits in an `overflow-x:auto` container with `min-width:560px`, so the table scrolls and the page does not |
| Loading and empty states | ✅ intentional empty states on an empty listing, empty cart and empty checkout; spinners while restoring the admin session |
| Uploaded image display | ✅ the image uploaded during acceptance renders on the product page, in the listing card and in Admin → Media |
| Public / Admin layout separation | ✅ no storefront header, footer or overlay appears under `/admin`; no admin chrome appears on public routes |
| Console errors | ✅ none on any route at any width |

### 5.1 Interactions actually driven at 390 px

Real clicks and a real key event dispatched through the DevTools Protocol, not asserted
from the markup. **11/11 passed.**

| Interaction | Result |
| --- | --- |
| Cart button opens the cart drawer | ✅ drawer content found and inside the viewport |
| Cart drawer at 390 px | ✅ 0 px overflow, 0 elements past the edge |
| `Escape` closes the cart drawer | ✅ drawer content gone afterwards |
| Search button opens the mobile search sheet | ✅ |
| Search sheet at 390 px | ✅ 0 px overflow |
| "التصفية" opens the filters sheet on `/shop` | ✅ "تصفية النتائج" visible and inside the viewport |
| Filters sheet at 390 px | ✅ 0 px overflow |
| "نظرة سريعة" opens quick view from a product card | ✅ its add-to-cart control visible and inside the viewport |
| Quick view at 390 px | ✅ 0 px overflow |
| Empty checkout form is refused | ✅ all four field-level Arabic messages shown: الاسم الكامل، رقم الهاتف، منطقة التوصيل، الشروط |
| No order is sent for an invalid form | ✅ no `POST /api/v1/orders` observed on the network |

## 6. What this does not cover

- One browser engine. Chrome/Blink only — no Firefox, no Safari/WebKit, no real iOS or
  Android device.
- Emulated viewports, not physical phones. Touch gestures, on-screen keyboards and
  browser chrome insets were not exercised.
- No interaction recording beyond form validation: hover states, animations and drag
  behaviour were not stepped through.
- Screenshots are session artefacts in the operator's scratch directory. They are
  deliberately not committed.

One cosmetic observation, deliberately **not** changed because it is not a defect and
touching it would be scope creep: Admin → Media renders a sub-kilobyte asset as
"0 كيلوبايت", since the size is floored to whole kilobytes. The acceptance upload was
511 bytes; a real product photo will never hit this.

## 7. Reproducing this

The instance is created exactly as `docs/client-lifecycle.md` describes, then:

```
alembic upgrade head
python -m scripts.instance_cli validate|plan|apply --profile <client>.yaml
python -m app.initial_data --email ... --password ...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
npm run dev
```

Then drive any browser at 390 / 768 / 1440 over the route table in §1 and §4. The check
that matters most is the one that found both defects: at each width, compare
`document.body.scrollWidth` with `document.documentElement.clientWidth`, and list every
element whose bounding box crosses the viewport edge. `overflow-x:hidden` on `html, body`
hides that overflow, so it will not show up as a scrollbar — only as content the customer
cannot reach.
