# The Tara Gallery storefront performance audit — 2026-09-18

## 1. EXECUTIVE SUMMARY

The dominant production problem is original image delivery, not a large third-party frontend framework. Multi-megabyte category artwork and camera photos are served to small cards, including the same 2,198,387-byte Hero on mobile and desktop. Implemented responsive WebP delivery for immutable registered uploads, smaller navigation/gallery thumbnails, independent Hero loading, one bounded showcase endpoint, compositor-based skeleton movement, and removal of two unnecessary initial browser operations.

No deployment, database migration, pricing/order/authentication/checkout rule changes, Admin implementation changes, or visual redesign occurred. Production remains unchanged. This is a validated local performance pass, **not a production readiness sign-off**: cold R2/cache behavior and equivalent staging browser measurements remain delivery gates.

Measurement boundaries: supplied production Lighthouse is the baseline. Targeted production browser/trace inspection used installed Edge; production API and public image bytes were captured read-only. Before/after build comparisons use the current checkout. Local browser comparisons replay captured public API data and pre-generated derivatives using the exact production image encoder; they do not measure real backend/database/R2 latency. The production JS hash differs from the locally built baseline, so neither local scores nor CPU timings establish a production improvement.

## 2. VERIFIED BOTTLENECKS

| Severity | Evidence / root cause | User impact | Exact files / endpoint | Solution / status |
|---|---|---|---|---|
| Critical | Production 22–28 MB baseline; category PNGs 2.46–3.21 MB, camera images up to 4.79 MB; no srcset | Slow 4G contention, late Hero, expensive decode | Media.jsx, CategoryCard.jsx, ProductCard.jsx, CategoryRail.jsx; uploaded originals | Responsive WebP endpoint and explicit sizes implemented; originals remain fallback |
| Important | Hero API settles before home sections but Promise.allSettled delays its rendering | Additional LCP discovery delay | HomePage.jsx /hero-slides /home-sections | Independently resolve both parallel requests; implemented |
| Important | Five production category_id requests; HomePage loops enabled categories | Linear round trips and repeated queries/state commits | HomePage.jsx; public_catalog.py /products | /home-showcases selects top four per active homepage category in one ranked query; implemented |
| Important | Production trace: CrRendererMain tasks 581 ms (429 ms layout) and 566 ms (562 ms React scheduler callback) at 4× CPU | Mobile loading / interaction stalls | Public shell + homepage render pipeline, production index-Bl7jHUTl.js | Reduce duplicate delivery and showcase commits; detailed React component attribution remains unverified; no speculative memoization |
| Moderate | Forced Layout 6.701 ms; stack at production script line 55, column 56306 maps to initial window.scrollTo | Unnecessary synchronous initial layout | PublicShell.jsx | Skip scroll when already at x=0/y=0; implemented; keep route resets when scrolled |
| Important | .vs-skel animates background-position during initial placeholders | Repeated painting on mobile | styles/public/base.css | Repeating gradient moved with pseudo-element transform; implemented; local Lighthouse reports no non-composited animations |
| Important | Cloudflare-injected module blocked by self-only script-src | Console/Issues noise; analytics unavailable | Production HTML / Cloudflare edge injection | Disable automatic beacon injection; documented, not executed; CSP unchanged |
| Moderate | Same logo URL has two production responses; measuring Image uses anonymous CORS, visible img uses normal mode | Duplicate 505,677-byte download | useLogoFit.js | Use CORS only for cross-origin canvas reads; implemented, replay two logo requests → one |
| Polish | Header name/tagline and active mobile tab have low contrast | Legibility / accessibility | Header.jsx, MobileTabBar.jsx, shell.css | Branding-sensitive color changes reserved for polish |

Already-correct behavior: one Hero in production; hidden slides already receive no src until activated. Below-fold product images already use lazy loading and media boxes reserve aspect ratios. CLS production baseline is zero. Navigation children mount only when expanded. Products are paginated; list/detail relationships use select-in loaders. No new database index is justified by measured evidence.

## 3. IMAGE PAYLOAD TABLE

Sorted by original file bytes, not duplicated DOM occurrences. Source URLs link to the exact production resources. D=1440×900, M=390×844. Natural dimensions include EXIF orientation; rendered dimensions come from production DOM measurements. CSS-hidden mobile rail images have zero rendered dimensions and are excluded from placement dimensions. Images further below the initial viewport were downloaded for inspection even if the initial browser had not requested them. An original appearing in both rail and card is one URL; multiple img elements do not alone prove duplicate transfer.

| Resource | Component | File size | Natural dimensions | Rendered dimensions | Format | Device | Above/below fold | Loading mode | Priority | Problem | Solution |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [9c3fd12e5c794b96a2e03f0d520c259e.jpg](https://media.the-taragallery.com/tara-store/9c3fd12e5c794b96a2e03f0d520c259e.jpg) | Homepage product showcase | 4,794,001 B (4682 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [759cc4f7de3247259e81e48d3b27f992.jpg](https://media.the-taragallery.com/tara-store/759cc4f7de3247259e81e48d3b27f992.jpg) | Homepage product showcase | 3,668,150 B (3582 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [2f630298bfe642a0b5529d23fc1c7806.png](https://media.the-taragallery.com/tara-store/2f630298bfe642a0b5529d23fc1c7806.png) | Category: Tara Sets | 3,211,760 B (3136 KiB) | 1122×1402 | D: 319×399, 38×38; M: 173×216 | PNG | D + M | Above / below (see placements) | eager + lazy rail | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [8a52f2dca94e4855bb8f02ddd65baa3a.jpg](https://media.the-taragallery.com/tara-store/8a52f2dca94e4855bb8f02ddd65baa3a.jpg) | Homepage product showcase | 3,065,486 B (2994 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [73c5a5b464b54ed38438b163d80ac623.png](https://media.the-taragallery.com/tara-store/73c5a5b464b54ed38438b163d80ac623.png) | Category: كوستر | 2,996,903 B (2927 KiB) | 1122×1402 | D: 274×421; M: 351×197 | PNG | D + M | Below | lazy | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [795e09c489db496ca58bec3172d91f84.png](https://media.the-taragallery.com/tara-store/795e09c489db496ca58bec3172d91f84.png) | Category: Crochet | 2,991,022 B (2921 KiB) | 1122×1402 | D: 319×399, 38×38; M: 173×216 | PNG | D + M | Above / below (see placements) | eager + lazy rail | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [b3657849bbc64d7a98051f9ee6da4812.jpg](https://media.the-taragallery.com/tara-store/b3657849bbc64d7a98051f9ee6da4812.jpg) | Homepage product showcase | 2,990,002 B (2920 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [f9a9c43c34994f5495effd12a6b19c78.png](https://media.the-taragallery.com/tara-store/f9a9c43c34994f5495effd12a6b19c78.png) | Category: Tara Gift Boxes | 2,542,918 B (2483 KiB) | 1122×1402 | D: 319×399, 38×38; M: 173×216 | PNG | D + M | Above / below (see placements) | eager + lazy rail | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [d2c680a81acc4a9091a94fc3536e9cc6.png](https://media.the-taragallery.com/tara-store/d2c680a81acc4a9091a94fc3536e9cc6.png) | Category: Candles | 2,459,689 B (2402 KiB) | 1122×1402 | D: 319×399, 38×38; M: 173×216 | PNG | D + M | Above / below (see placements) | eager + lazy rail | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [28f5c2c9054a433ca5b21010e3f3ffbd.png](https://media.the-taragallery.com/tara-store/28f5c2c9054a433ca5b21010e3f3ffbd.png) | Category: شموع تارا المميزة | 2,424,447 B (2368 KiB) | 1122×1402 | D: 274×421; M: 351×197 | PNG | D + M | Below | lazy | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [fb8286f4e0434125858a1a128473e191.png](https://media.the-taragallery.com/tara-store/fb8286f4e0434125858a1a128473e191.png) | Category: شمعة المشروبات | 2,269,650 B (2216 KiB) | 1122×1402 | D: 274×421; M: 351×197 | PNG | D + M | Below | lazy | auto | Original artwork in rail / cards | 96–2048w WebP, section sizes |
| [b985ff43c4f44ce4805007e024360f6c.jpg](https://media.the-taragallery.com/tara-store/b985ff43c4f44ce4805007e024360f6c.jpg) | Homepage product showcase | 2,248,497 B (2196 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [abd9e14abe744821a6cf1df2e655f61b.png](https://media.the-taragallery.com/tara-store/abd9e14abe744821a6cf1df2e655f61b.png) | Hero | 2,198,387 B (2147 KiB) | 2032×774 | D: 1376×524; M: 390×149 | PNG | D + M | Above | eager | high | 2.2 MB shared desktop/mobile original | Responsive WebP; eager/high retained |
| [61dfaf94c96e4aef81b5c6ff108399da.jpg](https://media.the-taragallery.com/tara-store/61dfaf94c96e4aef81b5c6ff108399da.jpg) | Homepage product showcase | 2,094,312 B (2045 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [ecaedacfbe0943ad8fc128da140c1544.png](https://media.the-taragallery.com/tara-store/ecaedacfbe0943ad8fc128da140c1544.png) | Homepage product showcase | 1,946,847 B (1901 KiB) | 1086×1448 | D: 194×194; M: 168×112 | PNG | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [45388a02217548b7b41a1c2a66cf30f8.png](https://media.the-taragallery.com/tara-store/45388a02217548b7b41a1c2a66cf30f8.png) | Homepage product showcase | 1,893,331 B (1849 KiB) | 1086×1448 | D: 194×194; M: 168×112 | PNG | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [a970ab5195cf4826821c063f4863760b.jpg](https://media.the-taragallery.com/tara-store/a970ab5195cf4826821c063f4863760b.jpg) | Homepage product showcase | 1,761,339 B (1720 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [96be835066694ad2b1e7e0429c00d68e.jpg](https://media.the-taragallery.com/tara-store/96be835066694ad2b1e7e0429c00d68e.jpg) | Homepage product showcase | 1,654,401 B (1616 KiB) | 3024×4032 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [1654262a4b11420d8925fee20075d04f.jpg](https://media.the-taragallery.com/tara-store/1654262a4b11420d8925fee20075d04f.jpg) | Homepage product showcase | 1,017,126 B (993 KiB) | 2508×2987 | D: 194×194; M: 168×112 | JPEG (MPO) | D + M | Below | lazy | auto | Original camera image / artwork in small card | Responsive WebP; preserve EXIF/framing |
| [tara-logo2.png](https://the-taragallery.com/branding/tara-logo2.png) | Header + footer logo | 505,677 B (494 KiB) | 1254×1254 | D: not visible; M: not visible | PNG | D + M | Above + below | auto | auto | 505 KB; duplicate CORS-mode fetch | Fetch mode corrected; optimize/version asset later |
| [tfn.png](https://the-taragallery.com/branding/tfn.png) | Footer credit | 84,872 B (83 KiB) | 513×226 | D: not visible; M: not visible | PNG | D + M | Below | auto | auto | 513px asset shown at 64px | Resize/version later (polish) |

The exact Hero at width 480 is 20,888 B versus 2,198,387 B. Category examples at width 480: d2c680… 76,554 B; 795e09… 90,970 B; 2f6302… 98,660 B. These are measured encoder outputs, **not a prediction of which width every browser will select**. Product examples: b36578… 33,502 B and 9c3fd1… 46,174 B at width 480. WebP quality 85, Lanczos resize, transparency, EXIF rotation and complete framing are preserved; actual animation falls back to the original. Camera MPO auxiliary frames are not treated as animation. No remote arbitrary-URL fetcher was introduced.

## 4. LCP ANALYSIS

Both inspected production viewports identify `.vs-hero__media > img.vs-media` in Hero.jsx, source `https://media.the-taragallery.com/tara-store/abd9e14abe744821a6cf1df2e655f61b.png`. Desktop rendered 1376×524; mobile 390×149. It is an img, not a CSS background, and is eager with high priority already. This is a client-rendered SPA, not an SSR hydration waterfall.

Targeted unthrottled production timeline: desktop Hero API starts 828 ms and settles about 914 ms, home sections settle about 935 ms, image starts 985 ms, image fetch lasts 1033 ms, observed LCP 2228 ms. Mobile image starts 535 ms, lasts 1077 ms, observed LCP 1648 ms. These timings are **not** the supplied slow-4G 18.3 s / desktop 3.5 s baseline and do not reconstruct that run's exact request timeline.

Root causes: discovery after JS and Hero API, an unnecessary wait for the sections API, and a 2.2 MB image competing with large category images. Fix: independently render Hero; responsive sources; keep first-slide eager/high. No preload was added: the record is runtime-managed, and speculative HTML preload would risk a wrong or duplicate resource. Only the first slide is high priority. Local post-change Lighthouse also identifies the Hero.

## 5. HOMEPAGE REQUEST MAP

| Request | Production count | Class | Dependency / decision |
|---|---:|---|---|
| /store/settings | 1 | Initially required | Identity, maintenance and storefront settings |
| /categories | 1 | Initially required | Shared shell navigation and category cards; includes children |
| /hero-slides | 1 | Initially required | Runs in parallel; no longer waits for sections |
| /home-sections | 1 | Initially required | Enables list sources; parallel with Hero |
| /delivery-areas | 1 | Deferrable | Globally loaded, needed for cart delivery notices / checkout; retained to avoid changing their readiness semantics |
| /products/featured?page_size=8 | 1 | Section-dependent | Starts after enabled sections; compact list payload |
| /products/new?page_size=8 | 1 | Section-dependent | Same; overlaps featured product data but not an identical query |
| /products/bestsellers?page_size=10 | 1 | Section-dependent | Empty production result; still required to discover emptiness |
| /products/packages?page_size=6 | 1 | Section-dependent | Empty production result; no package image transfer observed |
| /products?category_id=1,5,10,2,11&show_on_home=true&page_size=4 | 5 | Verified N+1 / category-dependent | Replaced with one /home-showcases request |

Before **14** data requests, after **10**, with current five showcase categories. General pattern 9 + N → 9 + 1 (no showcase request when N=0). New endpoint receives no arbitrary category list: server-owned active show_on_home categories determine the result. ROW_NUMBER partitions by category and preserves existing featured/sort_order/id ordering and availability. Existing list serializer/localization are reused. Regression tests show SQL SELECT count does not grow when categories increase from one to six. Image derivatives are image requests, not counted as homepage JSON data requests.

No separate navigation endpoint, category-tree duplicate, third-party widget request, or duplicate identical catalog request was observed on the homepage. Featured/new lists overlap product records; merging every homepage endpoint or caching business data is unnecessary for this pass. Delivery-area duplicate behavior on ShippingPolicyPage is a separate route-level reuse opportunity, not a verified homepage N+1.

## 6. MOBILE MAIN-THREAD ANALYSIS

The supplied mobile baseline remains TBT 1050 ms, 18 long tasks, about 7.7 s main-thread work / 1.9 s JS. Targeted 4× production trace verified substantial layout and React scheduler work. The forced initial scroll is precisely identified above. Skeleton background-position is a concrete paint cost. Numerous image decodes and independent showcase completions accompany initial rendering; their individual share of TBT was not isolated with a React Profiler, so no component-specific CPU saving is claimed.

Changed: responsive decode sizes, one showcase response/state completion, compositor skeleton animation, conditional initial scroll, duplicate logo request removal. Category tree is small (four production roots, 11 total categories), nested mobile children are conditional, scroll listener is passive, dialogs use focus trap/reference-counted scroll lock, Hero pauses in hidden tabs and respects reduced motion. The production trace's 6.701 ms synchronous layout stack maps to PublicShell's scroll reset, not a repeated scroll/resize measurement loop. Broad StoreContext updates exist, but expensive rerender attribution has not been established. No React.memo/useMemo/useCallback was added.

The original audit did not supply its eight/mobile and three/desktop failing animation node lists, so those exact nodes cannot be reconstructed from the baseline alone. The skeleton animation is verified in code; interaction-only box-shadow/color transitions remain unchanged. Local task/CPU timings vary markedly between runs, especially during concurrent audit/test activity; one mobile replay had more accumulated long-task time after changes. Treat mobile CPU as **remaining work**, not a solved issue. Profile on an idle staging host after warming derivatives and with component/source attribution enabled. The unrelated focus-trap offsetWidth/offsetHeight reads occur on dialog open/Tab and are not the initial forced-layout stack; they were preserved.

## 7. BUNDLE AUDIT

Production build before any edit: Vite 6.4.3, React 18.3.1, React Router 7.18.3-compatible installed dependency. Entries: src/main.jsx → App.jsx → locale routes → StoreProvider/PublicShell. AdminApp and catalog, categories, detail, cart, checkout and editorial routes use lazy imports. Homepage is eager. Backend is FastAPI/SQLAlchemy with SQLite development and MySQL compatibility; media providers are local filesystem and R2.

| Built resource | Before raw / gzip kB | After raw / gzip kB |
|---|---|---|
| Main JS | 297.69 / 97.20 | 298.89 / 97.73 |
| Main CSS | 104.06 / 19.43 | 104.26 / 19.45 |
| AdminApp | 169.37 / 44.27 | 169.37 / 44.27 |
| CatalogPage | 13.11 / 4.36 | 13.11 / 4.36 |
| CheckoutRoutePage | 10.69 / 3.85 | 10.69 / 3.85 |
| ProductDetailPage | 7.97 / 3.02 | 7.99 / 3.03 |

Small JS growth supplies responsive sources/fallbacks; it is outweighed by measured image reduction. Admin chunk is absent from production homepage requests and remains lazy and unchanged in size. No large editor/chart/dashboard/icon/font-locale packages or duplicate library families appear in package dependencies. Shared main contains React/router, storefront shell, provider, overlay and eager homepage code. Final local unused-JS details estimate 31,535 transfer bytes in the main script, rather than reproducing the supplied production 212 KiB estimate; the original full artifact and production bundle differ. Unused code estimates include functionality not exercised on initial navigation; do not remove it indiscriminately.

All public route CSS is bundled through styles/public/index.css; that explains route-specific unused rules. AdminApp has no imported Admin stylesheet leaking into this bundle. The supplied ~19 KiB unused CSS does not justify a broad refactor. Marcellus is used for the Latin brand name; Cairo 400/500/600 use swap, direct ~47–49 KB TTF each, about 144 KB total, with one-year font caching. No Roboto request is observed. Google Marcellus CSS and the hashed main CSS remain render-blocking. WOFF2/self-hosting and optional route CSS splitting are subsequent work, preserving typography.

Production cache inspection: hashed `/assets/index-Bl7jHUTl.js` and `/assets/index-B2dgD52K.css` already send `public, max-age=31536000, immutable`. Uploaded R2 images have the same policy. Cairo and Marcellus font binaries have one-year caching; Google Marcellus CSS is private with max-age=86400. `/branding/tara-logo2.png` (505,677 B), `/branding/tfn.png` (84,872 B), and `/branding/tara-favicon-32.png` (2,539 B) have max-age=14400. The branding resources are the confirmed short-lived image candidates; the supplied ~393 KiB savings estimate cannot be reconstructed exactly without the original Lighthouse artifact. Fingerprint their filenames before recommending immutable caching. Dynamic storefront JSON/business data was not cached. New derivative responses are immutable by original random key/width/encoder version.

## 8. CSP / CONSOLE FINDINGS

Blocked exact URL: `https://static.cloudflareinsights.com/beacon.min.js/v31edd6df95cf4e85bb4c19e7a9bdbcba1788362987495`.

Origin: `https://static.cloudflareinsights.com`; type: external module script / analytics beacon, third-party. Effective directive reported by SecurityPolicyViolationEvent: `script-src-elem`, falling back to the actual policy `script-src 'self'`. Source: a Cloudflare `data-cf-beacon` script appended to the production HTML response; it is not requested by a Tara React component or repository index.html. Impact: analytics does not initialize; storefront rendering/navigation does not require it.

Correct narrow solution for current behavior: disable automatic Cloudflare Web Analytics injection for this storefront. No script-src/connect-src expansion, wildcard, unsafe-eval or new unsafe-inline was added. This infrastructure action was documented only; changing the live Cloudflare configuration would violate the no-deploy/external-change boundary. If analytics is later intentionally required, review its exact script and telemetry origins and update only those directives.

No other exceptions/API failures/404s were observed in the initial production homepage sample. React 18 development testing emitted a fetchPriority unknown-prop warning; Media now uses lowercase fetchpriority while retaining the browser attribute. jsdom canvas warnings are an existing test-environment limitation, not production exceptions. Initial replay smoke 404s were missing category-banner/gallery fixture files; those exact production URLs returned 200 and were subsequently captured for complete validation. Do not treat these harness failures as production defects.

## 9. WEB VITALS

Supplied **production before**: mobile Performance 45, FCP 2.5 s, LCP 18.3 s, TBT 1050 ms, CLS 0, Speed Index 5.2 s. Desktop 79 / 0.7 s / 3.5 s / 0 ms / 0 / 1.3 s. **Production after: not measured; nothing deployed.**

Final Lighthouse 13.4.1 on local production builds with replayed API data and warm pre-generated images (same mobile Moto G Power/slow-4G configuration; desktop preset) produced:

| Metric | Local mobile after | Local desktop after |
|---|---:|---:|
| Performance | 48.00  | 91.00  |
| FCP | 2.80 s | 0.67 s |
| LCP | 9.87 s | 1.64 s |
| TBT | 943.25 ms | 128.00 ms |
| CLS | 0.069  | 0.002  |
| Speed Index | 3.20 s | 1.13 s |
| Main-thread work | 3.57 s | 0.94 s |

These are separate local measurements, **not valid production before→after pairs**. Local CLI wrote complete JSON reports but exited with Windows Edge temporary-profile cleanup EPERM; no Lighthouse page runtimeError was present. Earlier local mobile run scored 56 versus final 48, demonstrating CPU/measurement variance. The final local mobile CLS 0.069 is attributed by Lighthouse to Cairo font-loaded shifts; desktop 0.0016 is nonzero. Production baseline remains zero; verify this on staging before sign-off rather than claiming preserved measured CLS or making a speculative layout/font redesign.

Controlled browser replay comparison (bytes from response content-length; gzip static/API responses, original/derived image bytes; fonts remain external):

| Device | Total response bytes before → after | Image bytes before → after | JSON requests before → after | All responses before → after |
|---|---:|---:|---:|---:|
| mobile | 29,135,456 → 1,632,477 | 28,865,464 → 1,362,757 | 14 → 10 | 37 → 32 |
| desktop | 32,990,186 → 1,657,385 | 32,705,642 → 1,373,113 | 14 → 10 | 40 → 39 |

These are initial viewport + fixed post-idle window measurements, not a full-session CDN cost model. Native lazy thresholds/CPU timing affect which below-fold images arrive; mobile after can request different images. Full captured original inventory and fixed-width encoder measurements above provide a separate delivery-size comparison. ResourceTiming hides cross-origin CDN transfer sizes without Timing-Allow-Origin, so zero-valued production image timing bytes were **not** used to claim a small payload.

## 10. IMPLEMENTED CHANGES

| File | Change / reason | Impact / boundary |
|---|---|---|
| backend/app/api/v1/endpoints/public_catalog.py | Registered-upload image route; six allowed widths, provider ownership check, immutable WebP responses, persistent atomic disk cache, two encoder slots; ranked /home-showcases | Substantial smaller image responses; fixed query count; no URL fetch/DB migration |
| backend/app/services/media_thumbnails.py | Reusable quality-85 WebP resize, no upscale, EXIF/transparency, MPO frame zero, animation fallback, 25M-pixel decode bound | Original framing preserved; bounded processing; original URLs untouched |
| frontend/src/utils/responsiveImage.js | Responsive descriptors for immutable upload filenames; error fallback to original | Browser chooses device width; non-upload editorial assets unchanged |
| frontend/src/components/public/shell/Media.jsx | srcset/sizes in foreground/backdrop; conservative default 100vw; React 18 priority attribute | Shared responsive delivery, no gallery quality reduction from card-size defaults |
| frontend/src/components/public/catalog/CategoryCard.jsx | Explicit card sizes; showcase override | Small sources for 173/319 px cards |
| frontend/src/components/public/catalog/ProductCard.jsx | Explicit responsive card sizes | Smaller product images / decode surfaces |
| frontend/src/components/public/catalog/PackageCard.jsx | Explicit cover sizes | Preserves larger package-card quality; no production packages populated |
| frontend/src/components/public/home/Hero.jsx | Exact Hero sizes, link name and hidden-slide tab exclusion | Keeps first eager/high; accessible artwork links |
| frontend/src/components/public/navigation/CategoryRail.jsx | 38px responsive thumbnails + dimensions | 96px sources instead of 2–3 MB originals |
| frontend/src/components/public/navigation/CategoryDrawer.jsx | 46px responsive thumbnails + dimensions | Small drawer delivery; current appearance |
| frontend/src/components/public/product/Gallery.jsx | 76px thumbnail sizes | Thumbnails no longer use detail-width images |
| frontend/src/components/public/shell/PublicShell.jsx | Skip scrollTo when already at top | Removes exact unnecessary forced initial layout; resets scrolling routes |
| frontend/src/hooks/useLogoFit.js | CORS only for cross-origin measurements | Two logo responses → one in replay |
| frontend/src/pages/HomePage.jsx | Independent Hero/sections resolution, one showcase fetch, explicit large-showcase category sizes | Removes API barrier and N+1 requests/commits |
| frontend/src/api/publicApi.js; frontend/src/services/catalog.js | Public aggregated showcase adapter using existing product normalizer | Existing service architecture/localization retained |
| frontend/src/styles/public/base.css | Move repeating skeleton gradient with transform | No non-composited initial animation reported locally |
| backend/tests/test_storefront_performance.py | Delivery/cache/width/registered-source, selection equivalence, MPO, animation, constant SQL-query tests | Regressions and bounded processing verified |
| frontend/src/test/homePerformance.test.jsx; catalogUxPartB.test.jsx; utils.jsx | Responsive fallback, aggregated request and initial-scroll tests; update affected fixtures | Endpoint contract and storefront behavior verified |

## 11. RECOMMENDED NEXT PERFORMANCE WORK

**P0 — before delivery:** Validate the actual hosting path for /api/v1/storefront-media: writable persistent cache directory, R2 read permissions, original fallback behavior, and cache persistence across releases/workers. Warm first Hero plus above-fold category/rail widths using registered uploads in the real staging runtime; compare cold/warm backend latency and concurrency. Run equivalent idle-host production-like Lighthouse and network tests before delivery. These are release validation gates for material delivery work, not micro-optimizations. Current local replay bypasses cold storage conversion and cannot prove server capacity.

**P1 — meaningful:** Attribute remaining mobile React/layout tasks with source/component profiling, after removing audit/test contention. Resolve local font-swap CLS and external font render dependency if reproduced on staging. Disable Cloudflare's unnecessary automatic beacon injection; preserve existing CSP. Consider generating immutable derivative objects asynchronously at upload/backfill time and serving through existing R2/CDN if cold conversion or API image traffic burdens hosting; this larger change is intentionally not implemented. Measure and reuse/defer delivery areas without changing cart/checkout readiness semantics.

**P2 — optional:** Lossless/appropriately sized fingerprinted branding assets; WOFF2 Cairo with required weights/subsets and unchanged typography; homepage/overlay or route CSS splitting only if measured execution/byte savings justify it; update stale navigation/free-shipping tests to current approved UI. No speculative DB index, caching business data, or indiscriminate memoization.

## 12. FRONTEND POLISH BACKLOG

| Page/component | Problem / reason | Breakpoint | Likely source | Recommended fix | Severity |
|---|---|---|---|---|---|
| Header brand name | Tara foreground #ae98cb on near-white, contrast 2.55; large-text target 3 | Desktop | Header.jsx; shell.css / brand tokens | Agree darker brand text variant while preserving identity | Polish |
| Header tagline | #ae9acb on near-white, 2.51; 11.5px requires 4.5 | Desktop | Header.jsx; shell.css | Approved readable muted-text variant | Polish |
| Active bottom tab | #ae98cb on near-white, 2.55; 11px requires 4.5 | Mobile | MobileTabBar.jsx; shell.css | Accessible active-label treatment | Polish |
| Cairo font swap | Final local LH mobile CLS 0.069, font-loaded shifts; not established as production regression | Cold mobile load | tokens.css; font delivery | Verify with idle staging trace; preserve Cairo; optimize delivery/fallback metrics only if reproducible | Moderate |
| Homepage showcase category artwork | Portrait category art is cropped into a mobile landscape showcase; verify intended visible artwork content | Mobile | HomePage.jsx; home.css / CategoryCard.jsx | Review crop/content in final polish; do not change approved ratio during performance pass | Polish |
| Validation fixtures | Three existing tests expect removed shipping header and separate mobile category drawer | Test-only | freeShippingBar.test.jsx; publicShell.test.jsx | Align expectations with approved consolidated navigation and delivery UI | Moderate |

The artwork-only Hero link had no visible text, alt text or aria-label in the pre-change component; it and hidden-slide keyboard focus were trivially corrected. Local link-name audit now passes. No measured horizontal overflow was found at audited desktop/mobile sizes. Blank regions in an unscrolled full-page screenshot are pending viewport entrance effects; scrolling validation is required and they are not automatically a layout defect. Long-tree/root scanning and focus/background interaction require broader accessibility review during polish; current root-only expansion, trap, Escape and scroll lock are preserved.

## 13. VALIDATION

- Before and after production builds pass; final resource sizes above. No lint/typecheck script, TypeScript project, or ESLint configuration exists in the inspected frontend package; no fictitious lint/typecheck pass is claimed. `git diff --check` passes.
- Full frontend suite: initial run 306/310 tests passed; one failed showcase fixture was updated for the new contract. Three other failures reproduced with the unmodified PublicShell: two obsolete free-shipping-bar expectations and one obsolete separate-category-drawer expectation. Final targeted seven suites **41 tests pass**, including Admin theme boundary. Do not claim the entire existing suite is green.
- Final selected backend catalog/media/maintenance/performance suite **79 tests pass**; expanded performance suite **5 tests pass**, including constant SELECT count from one to six categories. Starlette/httpx test-client deprecation warning remains; unrelated dependency migration not attempted.
- Desktop/mobile browser smoke uses production build with captured public GET data, not a real checkout backend. Homepage, categories, listing, detail, search, empty cart/checkout entry and Admin login were exercised. Add-to-cart/variant/coupon/checkout behavior is covered by existing unit suites; no live purchase/order was submitted.
- Mobile menu opens one dialog, keeps body overflow hidden, and closes with Escape. Responsive media framing/EXIF was inspected; page scroll reveals below-fold sections. Original fallbacks and immutable cache reuse are tested. No Admin implementation files changed.
- Local Lighthouse complete JSON exists for mobile/desktop; cleanup EPERM is a tool exit failure, not a successful command exit. Results and limitations above. CSP issue remains on the live site until edge injection is disabled; no deployment occurred.
- Final browser smoke: **19 recorded checks**, covering nine routes at both desktop/mobile and the mobile drawer, with **zero console exceptions/errors, zero failed responses, zero broken loaded images and zero horizontal overflow** after completing the public fixtures. These are replay smoke checks, not live order validation. Early fixture misses were checked against production (all 200) and corrected in the harness, not suppressed in app code. The last build and an additional two relevant frontend suites (11 tests) passed after the drawer thumbnail update.

## 14. FILES CHANGED

- `backend/app/api/v1/endpoints/public_catalog.py`
- `backend/app/services/media_thumbnails.py`
- `backend/tests/test_storefront_performance.py`
- `docs/qa/storefront-performance-audit-2026-09-18.md`
- `frontend/src/api/publicApi.js`
- `frontend/src/components/public/catalog/CategoryCard.jsx`
- `frontend/src/components/public/catalog/PackageCard.jsx`
- `frontend/src/components/public/catalog/ProductCard.jsx`
- `frontend/src/components/public/home/Hero.jsx`
- `frontend/src/components/public/navigation/CategoryDrawer.jsx`
- `frontend/src/components/public/navigation/CategoryRail.jsx`
- `frontend/src/components/public/product/Gallery.jsx`
- `frontend/src/components/public/shell/Media.jsx`
- `frontend/src/components/public/shell/PublicShell.jsx`
- `frontend/src/hooks/useLogoFit.js`
- `frontend/src/pages/HomePage.jsx`
- `frontend/src/services/catalog.js`
- `frontend/src/styles/public/base.css`
- `frontend/src/test/catalogUxPartB.test.jsx`
- `frontend/src/test/homePerformance.test.jsx`
- `frontend/src/test/utils.jsx`
- `frontend/src/utils/responsiveImage.js`
