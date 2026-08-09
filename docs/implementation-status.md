# Implementation status

## Storefront visual correction: header, logo, rail, hero, theme — 2026-08-03

**Branch:** `fix/vista-reference-alignment`. **Not merged, not pushed.** One
focused correction pass on the owner's screenshot feedback. No route, feature or
component was added or removed, and the storefront was not redesigned. Full
measurements and the browser evidence: [qa/vista-reference-alignment.md](qa/vista-reference-alignment.md) § Pass 2.

| Complaint | Result |
| --- | --- |
| The white header band is too tall and visually empty | Desktop header **128px → 110px** (64px identity + 46px navigation). Logo, search and cart now share one horizontal axis (mid-lines all at 31.5px). The empty stretch was the search field stopping at 620px in a store with no phone number; its cap is now one token, `--vs-search-max`, at 820px. Sticky behaviour and every control kept |
| The logo's own whitespace makes the mark tiny | The file is untouched. Header and footer clip it to a fixed viewport and `useLogoFit` scales the image inside so the artwork fills it. Visible mark **29.3 × 14.4 → 87.9 × 43.2** at desktop (3.0×) and **20.7 × 10.2 → 65.0 × 32.0** at 390/768 (3.1×), aspect ratio exact. `StoreSettings.logo_url` is still the only source |
| The rail reads as a second navigation bar of purple blocks | White, 64px, a hairline and a near-invisible shadow. The one saturated element is the dark-purple trigger. Items are the categories' own pictures — 8 of 8 at 1440, 0 gradient stand-ins — with a neutral line icon where a category has no image, and a pale-yellow active state |
| The hero looks like a rounded card in a padded container | The band left the container: radius **22 → 0**, gutters and the 20px above it removed. It now takes **100%** of the storefront width at every viewport (was 93% at 1440, 73% at 1920), stopping exactly at the rail's edge. A new `--vs-hero-max-h` keeps a 1856px band from becoming a 700px wall |
| Advertisements are overprinted with a second headline | A slide with an image and no supporting copy (no subtitle, description or button) is treated as a finished advertisement: image only, no veil, no CTA; its title stays the Admin label and the `alt` text. No column, no migration, no hard-coded slide id. The preview dataset now carries one such slide |
| Too much solid purple | The homepage editorial panel went from a purple slab to a white surface with one Vista-yellow rule; its button took the purple instead. The package badge stopped using the template's original teal and now derives from `--vs-primary`. Navigation band shortened, section rhythm tightened 68/40 → 56/34 |

**Verification.** Frontend Vitest **106/106** (7 new tests), production build
clean, `backend/tests/test_preview_dataset.py` **18/18** — the only backend-side
change was one record in `instance/preview/vista-social-preview.yaml`; no backend
Python file was touched. Chrome sweep at 390 / 768 / 1440 / 1920 plus the
scrolled header, the image-only slide, the collapsed rail, the category drawer,
the mobile menu and `/admin`: **no horizontal overflow anywhere, and 0 elements
carrying a `vs-` class on any admin route.**

**Still blocked on the owner.** The preview artwork is eight variations of one
purple-to-gold gradient, so at 40px the rail's thumbnails read as coloured
squares rather than as distinguishable categories. No image was generated or
downloaded. Real category photographs and a trimmed, transparent logo are what
close the remaining distance to the reference.

## Storage repair, invoice print pagination and live MySQL acceptance — 2026-08-02

**Branch:** `feat/vista-preview-data-storage`. **Not merged, not pushed.** This closes the
three technical gaps the visual QA left open. No feature was added.

| Gap | State |
| --- | --- |
| Preview seed trusted the database row and reported "already uploaded" for a missing object | **Closed.** `StorageProvider` gained `exists()` and `restore()`; the seed now verifies the row **and** the object, and repairs the object at its recorded key |
| A 12-line invoice split its totals block across an A4 page break | **Closed.** Print-layout only; short and 12-line invoices are now one clean page, and the closing block never splits |
| MySQL runtime acceptance was BLOCKED on Docker | **Closed.** Run against the machine's own MySQL **8.0.46** in an isolated `vista_store_dev`; 22 of 22 acceptance steps passed |

### 1. Storage repair

`StorageProvider` is now a four-method boundary — `save`, `exists`, `restore`, `delete`.

* `LocalStorageProvider.exists()` stats the file inside the media root and returns `False`
  (never raises) for an empty key or one that resolves outside it.
* `R2StorageProvider.exists()` was already present; it now **refuses to issue a request at
  all** for a key outside `R2_OBJECT_PREFIX` and reports it absent. `restore()` refuses
  such a key outright, the same rule `delete()` already enforced.
* `restore(key, data, content_type=…)` deliberately does **not** mint a key. Writing back
  to the recorded key is what lets the seed repair storage without touching the database
  row — no duplicate `MediaAsset`, and no URL already published in a category, product,
  hero slide or banner changes.

`PreviewImporter._verify_media_object` runs for every owned, unedited media row and adds a
new `repair` outcome to the plan. It refuses three cases before it looks at anything:
an owner-edited row, a row uploaded to a different provider than the one now configured,
and a key outside the batch's own media prefix — the last is never even probed. Because
the placeholder bytes are deterministic, a repair reproduces the object byte for byte.

Eight regression tests in `backend/tests/test_preview_importer.py` (row+object present →
skip; object missing → repair; no second row or batch record; the repaired object is
readable at its published URL and the category still points at it; an owner-edited row is
never repaired; unrelated owner media untouched; a repair is itself idempotent) and six in
`backend/tests/test_storage_providers.py` (local `exists`/`restore` round trip, `exists`
false outside the media root, R2 `restore` keeps the key and URL, R2 `restore` refuses a
foreign prefix, `exists` never probes a foreign key).

### 2. Invoice print pagination

Print CSS and the existing markup only — no redesign, no smaller type. Full result and
the measured page table: [client/preview-visual-qa.md](client/preview-visual-qa.md) §4a.

Three things were wrong, not one:

1. The totals, notes and cancellation notice were three siblings, so a page break could
   land between them. They are now one `.invoice-summary` with `break-inside: avoid`.
2. `visibility: hidden` blanked the admin chrome but left its boxes in flow, so a tall
   card *below* the sheet printed an **empty second page on every non-cancelled invoice**.
   `.no-print` is now a global print rule and is applied to that chrome.
3. `overflow: hidden` on the sheet — needed on screen to clip the watermark — truncated
   anything past page 1 when printing. Print restores `overflow: visible`, and the
   watermark is pinned to the page box instead, so it marks every page.

Verified by rendering the real component for five fixtures and paginating each with local
Chrome (`--headless=new --print-to-pdf`), then reading page assignment back out of the
PDFs: short 1 page, 12-line 1 page, 24-line 2 pages with the whole totals block on page 2,
cancelled 12-line 1 page, cancelled 24-line 2 pages with the watermark on **both**. The
`SKU` column header appears on page 2 of the 24-line PDF, so the repeating `thead` holds.
Two frontend regression tests lock it in.

### 3. Live MySQL acceptance — PASSED

MySQL **8.0.46**, `127.0.0.1:3306`, database `vista_store_dev`, application user
`vista_store_dev_user` whose grants reach that database and nothing else. The application
was never run as `root`. The SQLite-backed `uvicorn` was stopped first, and the MySQL URL
was supplied as a process environment variable — `backend/.env` still points at SQLite.

All 22 steps passed. Full table:
[deployment/mysql-local-development.md](deployment/mysql-local-development.md).
Highlights: Alembic reached **`0004_import_batches (head)`** on an empty database (30
tables, all InnoDB/utf8mb4, 23 FKs); `create=54` then `skip=53, update=1`;
`DECIMAL(12,2)` keeps `exponent == -2` and `SUM(price)` returns a `Decimal`; Arabic
including `ﷺ` survives utf8mb4; the three `json` columns round-trip and none is indexed;
a dangling FK and a duplicate slug are both refused; one COD order → **exactly one
invoice**, six further status transitions minted **no** second invoice, cancelling
restored stock `7 → 10` and preserved the invoice number; deleting one owned preview
object then re-seeding gave `repair=1` with the media row count unchanged; purge dry run
`delete=53`, applied `delete=66`, re-seed `create=54`.

**One genuine test defect was fixed, and it was not a MySQL compatibility defect.** Four
tests in `tests_mysql/test_mysql_preview.py` resolved their subject as "the first row of
this table". Against the empty CI service container that is the row they created; against
a real development database it is somebody else's — one failed outright. They now resolve
every row through the `ImportBatchRecord` that owns it, which is the rule the importer
itself uses. No application code needed a MySQL fix.

**SQLite is unaffected:** the full backend suite still runs on SQLite with no MySQL server
present, and `backend/.env` is unchanged.

### Verification (all run at the end of this session)

| Check | Command | Result |
| --- | --- | --- |
| Backend suite + coverage | `pytest --cov=app --cov=scripts` | **275 passed**, **89 %** (5167 statements, 563 missed) |
| MySQL integration suite | `pytest tests_mysql` against local MySQL 8.0.46 | **18 passed, 4 skipped** — the 4 need a second and third database |
| Frontend suite | `npx vitest run` | **55 passed** (5 files) |
| Frontend build | `npm run build` | clean — 88 modules, 407.80 kB JS / 111.62 kB gzip, 2.71 s |
| Focused invoice print | real component → Chrome `--print-to-pdf` → PDF page analysis | **5/5 fixtures pass**; totals block never split |
| Preview media repair | delete an owned object, re-seed, against MySQL | `repair=1`, object restored at the same key, no duplicate row |
| Whitespace | `git diff --check` | clean |
| Secret scan | pattern sweep over every tracked file | no credential value; `.env.mysql.local` confirmed ignored and untracked |
| Runtime-file tracking | `git ls-files` filtered | only `.example` templates and `backend/data/vista-uploads/.gitkeep` |

### Still blocked

* **Live R2 smoke test — BLOCKED, unchanged.** No `R2_*` value is set in `backend/.env` or
  in the environment, so no object has yet been written to a real bucket. The provider is
  implemented and unit-tested against a stub, and this session extended that stub coverage
  to `exists()` and `restore()`. Steps to finish:
  [deployment/r2-preview-setup.md](deployment/r2-preview-setup.md) §3. Scope was not
  changed to work around this.
* **Four `tests_mysql` tests — BLOCKED on a database-creating account.** They need
  `MYSQL_LIFECYCLE_URL` and `MYSQL_SEED_URL` pointing at two further schemas. The
  `MYSQL_ADMIN_PASSWORD` recorded in `.env.mysql.local` is rejected by the server
  (`ERROR 1045`), so the schemas could not be created. Exact variable names and the
  `CREATE DATABASE` / `GRANT` statements:
  [deployment/mysql-local-development.md](deployment/mysql-local-development.md).

### Next, in order

1. **Supply a working MySQL admin password**, create `vista_store_dev_lifecycle` and
   `vista_store_dev_seed`, and clear the last four skips.
2. **Supply R2 credentials** and run the live upload/read/delete smoke test.
3. **Send the owner [client/data-needed-from-owner.md](client/data-needed-from-owner.md).**
4. **Settle the currency before the first real order.**

---

## Preview catalog, R2 storage and MySQL runtime — 2026-08-02

**Branch:** `feat/vista-preview-data-storage`, cut from `feat/vista-store-initial-release`
at `db16863`. **Not merged, not pushed** — this repository has no `origin` remote, only
the read-only `template-upstream`.

| Phase | State |
| --- | --- |
| 1. Social source audit | **Done** — Instagram readable, Facebook still login-walled. [client/social-source-audit.md](client/social-source-audit.md) |
| 2. Preview dataset | **Done** — `instance/preview/vista-social-preview.yaml`: 7 categories, 25 products, 12 media, 1 delivery area, 3 hero slides, 2 banners, 1 coupon |
| 3. Preview batch lifecycle | **Done** — `import_batches` / `import_batch_records`, revision `0004`, `vista-preview validate/plan/seed/status/purge` |
| 4. R2 storage provider | **Done as code**, **live verification BLOCKED** — no credentials in this environment |
| 5. MySQL development runtime | **Done as configuration**, live verification BLOCKED at the time — Docker not installed. **Since passed on 2026-08-02 against local MySQL 8.0.46**; see the section at the top of this file |
| 6. Storefront preview notice | **Done** — `VITE_PREVIEW_NOTICE`, absent from the bundle when unset |
| 7. Visual QA | **Done — 2026-08-02.** All 16 public and admin routes opened in real Chrome at 390 / 768 / 1440 px against the populated preview catalog; full product → cart → COD checkout → admin confirm → invoice → A4 print flow driven through the UI. One storefront defect found and fixed. [client/preview-visual-qa.md](client/preview-visual-qa.md) |

### Verification (all run in this session)

| Check | Command | Result |
| --- | --- | --- |
| Backend suite + coverage | `pytest --cov=app` | **260 passed**, **91 %** (baseline 193), 5:07 |
| Frontend suite | `npx vitest run` | **53 passed** (baseline 47) |
| Frontend build | `npm run build` | clean, 405.68 kB JS / 110.91 kB gzip |
| Preview notice toggle | two builds | string present when configured, **absent from the bundle** when not |
| MySQL portability gate | `python -m scripts.mysql_compat --verbose` | **8 checks, 0 failures, 0 warnings**, head `0004_import_batches`, 29 tables |
| Alembic on a clean database | `alembic upgrade head` | `0001 → 0002 → 0003 → 0004` |
| Preview seed / idempotency | `vista-preview seed` ×3 | `create=54`, then `skip=53, update=1` twice — the single update is the batch's own seed counter |
| Preview purge, dry run | `vista-preview purge` | `delete=53`, nothing written |
| Preview purge, applied | `vista-preview purge --confirm` | `delete=66` (53 rows + 12 storage objects + the batch); status then reports the batch gone |
| Re-seed after purge | `vista-preview seed` | `create=54`, `seed_count` back to 1 |
| **Live storefront over HTTP** | operator script, uvicorn + seeded SQLite | **39/39 checks** |
| **Routes through the real Vite dev server** | 19 SPA routes + 8 proxied API paths + media | **28/28 reachable** |
| Whitespace | `git diff --check` | clean |
| Tracked-file hygiene | `git ls-files` filtered | no `.env`, `*.db`, `node_modules/`, `dist/`, `.venv/`, coverage artefacts; the only `.env*` files tracked are six `.example` templates |
| Secret scan | pattern sweep over every tracked file | no credential value — every hit is a variable name, an empty default or a test stub |

The live pass proved, among other things: a client-supplied `unit_price` of 1 is ignored
and the order totals 190; `payment_method: card` is refused with 422; confirming the order
issued exactly one invoice, `INV-000001`, matching the order total; the preview coupon
discounts server-side; and the preview delivery area is the only one, labelled and priced
at zero.

### Two defects found and fixed while exercising live data

1. **A sale was being mistaken for an owner edit.** `stock_quantity` was in the row
   fingerprint, so buying a preview product made it look edited — `purge` then skipped it
   with a misleading reason and left it behind. Stock is now excluded.
2. **`--force` bypassed the never-delete guard.** The refusal that protects a product an
   order references ran only on the not-edited branch, so a forced purge of an edited row
   walked straight past it. The guard now runs first, for every row, and no flag overrides
   it.

Both have regression tests.

### Blocked, and honestly so

* **Live R2 smoke test — BLOCKED.** `backend/.env` carries the `R2_*` keys empty and no
  `R2_*` variable is set in the environment. The provider is implemented and unit-tested
  against a stub; **no object has ever been written to a real bucket.** Exact steps to
  finish: [deployment/r2-preview-setup.md](deployment/r2-preview-setup.md).
* **MySQL runtime acceptance — BLOCKED.** Docker is not installed (`docker --version`
  unavailable; no install under `%ProgramFiles%\Docker` or `%LOCALAPPDATA%\Docker`).
  Nothing was installed to work around it and no existing MySQL server was contacted. The
  13-step sequence is written and ready: [deployment/mysql-local-development.md](deployment/mysql-local-development.md).
Visual QA was the third blocked item here. **It is no longer blocked** — see the
2026-08-02 pass below.

### Visual QA — done 2026-08-02

Driven with the locally installed Chrome over the DevTools Protocol from the backend
virtualenv (`websockets` + `httpx`, both already present). No Playwright, no Puppeteer and
no browser download.

| Check | Result |
| --- | --- |
| 16 routes × 390 / 768 / 1440 px | **48/48 inspected**, `dir="rtl"` and **0 px horizontal overflow** everywhere |
| Product → cart → COD checkout | **Pass** — `ORD-260802-7868`, 190 ₪, through the UI |
| Admin login → confirm → invoice | **Pass** — exactly one invoice per order; a `confirmed → processing → confirmed` round trip minted no duplicate |
| Invoice A4 print | **Pass** — 1-line invoice = one A4 page; no admin chrome prints; repeated table header on page 2 confirmed with `pdftotext` on the real 24-line PDF |
| Cancelled watermark | **Pass** — diagonal «ملغاة» prints without obscuring the figures |
| No card-payment UI | **Pass** — two radios only, COD and manual transfer |
| Public/Admin separation | **Pass** — no storefront chrome and no preview notice on any admin route |

**One storefront defect found and fixed:** the product-detail «الوصف» and «المواصفات»
tabs rendered empty white panels, because 23 of 25 preview products carry no
`description` and 22 of 25 carry no specifications. The description now falls back to
`short_description` and both panels have an empty state.

**One environment defect found, repaired, and reported rather than fixed:** all 12 preview
media objects were missing from `backend/data/vista-uploads/` and returned HTTP 404, so
every card, hero and banner painted blank. The deterministic placeholder bytes were
rewritten under their recorded keys. `preview_cli seed` **cannot** repair this — it decides
from the database row alone and reports "already uploaded" for objects that do not exist.
Fixing that needs an `exists()` on the `StorageProvider` boundary, which was out of scope
for a visual-QA pass.

Re-verified after the fix:

| Check | Command | Result |
| --- | --- | --- |
| Backend suite | `python -m pytest` | **260 passed**, 1 warning |
| Frontend suite | `npx vitest run` | **53 passed** (5 files) |
| Frontend build | `npm run build` | clean — 88 modules, `index-CAGMzJi6.js` 406.03 kB (gzip 110.98 kB), 4.27 s |
| Whitespace | `git diff --check` | clean |

### Next, in order

*Items 1 and 3 were done on 2026-08-02 — see the section at the top of this file. Item 3
was settled without Docker, against the machine's own MySQL 8.0.46.*

1. ~~**Give `StorageProvider` an `exists()` and make `_seed_media` re-upload a missing
   object**~~ — done.
2. **Supply R2 credentials** and run the smoke test in
   [deployment/r2-preview-setup.md](deployment/r2-preview-setup.md) §3. *Still open.*
3. ~~**Install Docker** and run the 13-step sequence~~ — done, without Docker, in
   [deployment/mysql-local-development.md](deployment/mysql-local-development.md).
4. **Send the owner [client/data-needed-from-owner.md](client/data-needed-from-owner.md).**
   The preview catalog buys time; it does not replace a single item on that list.
5. **Settle the currency before the first real order.** Still unverified, still expensive
   to change once an invoice exists.

### The exact command to remove the preview

```
cd backend
.venv\Scripts\python.exe -m scripts.preview_cli purge            # dry run
.venv\Scripts\python.exe -m scripts.preview_cli purge --confirm  # apply
```

---

## Vista Store client instance — 2026-08-02

**Branch:** `feat/vista-store-initial-release` · **Not merged, not pushed.**

Built from the Golden Commerce Template at `dba6a67` (v0.3.0-rc.1) — see
[template-origin.md](template-origin.md). Everything below the horizontal rule is the
template's own history and is left as written.

| Phase | State |
| --- | --- |
| 1. Clone and provenance | **Done** — independent repo, history preserved, `template-upstream` remote, no `origin` |
| 2. Facebook source audit | **Done** — page login-walled; only the bilingual name confirmed; gaps documented |
| 3. Client identity | **Done** — `instance/vista-store.yaml`, verified values only |
| 4. Catalog data | **Done, and empty by design** — no product was verifiable, so none was invented |
| 5. Payments | **Done** — COD + manual only; card/online rejected with 422; no card UI anywhere |
| 6. Invoices | **Done** — models, migration `0003`, service, admin API, admin screens, print layout |
| 7. Local storage | **Done** — Vista media root, Git-ignored; seed brand assets kept separate |
| 8. Local instance | **Done** — 26/26 live checks on a clean SQLite instance |
| 9. Visual QA | **NOT DONE** — no browser tooling available. Manual checklist in [client/local-acceptance.md](client/local-acceptance.md) |
| 10. cPanel readiness | **Done as documentation** — checklist, handoff, env template, release script. No deployment performed |

### Verification

- Backend `pytest --cov=app`: **193 passed**, 91% coverage (baseline 134)
- Frontend `vitest run`: **47 passed** (baseline 24)
- `npm run build`: clean — 87 modules, 405 kB JS / 111 kB gzip
- `python -m scripts.mysql_compat --verbose`: 8 checks, 0 failures, 0 warnings
- Live acceptance against a running server: 26/26

No existing test was weakened or skipped.

### Commits

```
c5dace2  feat(vista): client identity, local instance and cPanel readiness
8fdf4f5  feat(admin): invoice list, printable invoice sheet and payment visibility
08ecfe7  feat(invoices): issue an immutable invoice when an order is confirmed
8e87c2a  docs: record template provenance and the Facebook source audit
```

### Next, in order

1. **Send the owner [client/data-needed-from-owner.md](client/data-needed-from-owner.md).**
   Nothing else unblocks the store. Items 1–8 are hard blockers: without a delivery area
   no customer can complete checkout.
2. **Send the host [deployment/cpanel-capability-checklist.md](deployment/cpanel-capability-checklist.md).**
   Questions A1, A2 and A4 decide whether cPanel deployment is possible at all.
3. **Do the visual QA** in a real browser at 390 / 768 / 1440px. Test the printed invoice
   with more than 15 line items — that is where the first page break happens.
4. **Settle the currency and the invoice prefix** before the first confirmed order. Both
   become expensive once invoices exist.
5. Then load the real catalog and branding, and re-run acceptance against it.

### Decisions worth remembering

- **Facebook was not worked around.** No search fallback, no similarly-named page, no
  plausible placeholder. A blank field is a real blank.
- **No Passenger/WSGI adapter was written** — it would be untested against an environment
  nobody has described yet, which is worse than nothing.
- **Invoice cancellation routes through order cancellation**, so the two can never
  disagree and stock restoration stays in a single code path.
- **One invoice per order is a database constraint**, not only a service-level check.

---

# Template history — full-stack commerce MVP

**Authoritative handoff document.** Rewritten 2026-08-01 at the end of the continuation
session. Every figure below was produced by a command run in that session against this
repository; none of it is from memory or carried over unverified from the previous
handoff.

> **Superseded in part by the 0.3.0-rc.1 acceptance pass** (branch
> `feat/template-acceptance-rc`, 2026-08-01). That pass created a clean client instance
> from scratch, completed maintenance mode, performed browser acceptance in real Chrome
> and added an ephemeral MySQL 8 CI gate. Current gate-by-gate status is in
> [acceptance/release-candidate-report.md](acceptance/release-candidate-report.md), and
> the route-by-route visual record is in [acceptance/visual-qa.md](acceptance/visual-qa.md).
> §10, §11 and §15 below have been corrected accordingly; the rest describes the MVP
> session that produced the code and is left as written.

---

## 1. Objective

Turn the reusable commerce template into a complete, locally functional full-stack MVP:
the existing React/JSX Arabic-RTL storefront connected to a real FastAPI + SQLAlchemy +
Alembic backend on local SQLite, with admin authentication and roles, a functional admin
workspace, guest checkout, order management, local media uploads, seeded demo data,
automated tests, accurate documentation and inactive deployment templates.

**Product model:** one independent instance per client. No multi-tenancy, no `tenant_id`,
no shared SaaS database, no client branding in the template.

**Current state: the MVP scope is complete and verified.** The remaining items in §10 and
§11 are documented limitations and deliberate exclusions, not unfinished tasks.

---

## 2. Git state (verified at the end of the session)

| Item | Value |
| --- | --- |
| Working branch | `feat/fullstack-commerce-mvp` |
| HEAD | the commit carrying this document — `docs: record verified completion of the commerce MVP`. A commit cannot contain its own hash; resolve it with `git rev-parse --short HEAD` |
| Upstream | `origin/feat/fullstack-commerce-mvp`, pushed |
| Working tree | clean |
| `git diff --check` | clean |
| Tracked files | 163 |

### Commits added by the continuation session

```
1651ce0  test: scope ambiguous storefront and admin queries
46bb057  fix(config): make the documented .env format actually loadable
b0a0049  docs(deployment): add inactive per-client deployment templates
37680ac  docs: document the commerce template
<this>   docs: record verified completion of the commerce MVP
```

They sit on top of `bbaa7f7` (`wip: preserve fullstack commerce implementation state`),
which was **not** amended or rewritten.

### Sibling branches — untouched

```
  feat/backend-foundation      2c418a4
  feat/frontend-foundation     f2ddd6e  [origin/feat/frontend-foundation]
  main                         0c6ff5d  [origin/main]
```

**Important correction to the previous handoff.** The earlier document recorded `main` at
`2c418a4` and this branch as never pushed. Both statements were out of date before the
continuation session began. At session start the actual state was already:

- `main` = `origin/main` = `0c6ff5decdfa0d84b5db5bce95e6cf7c1a60a276` (`..`)
- `origin/feat/fullstack-commerce-mvp` = `bbaa7f7`, already pushed

The continuation session **did not create, modify, merge into or push `main`**. It read
`main`'s hash and nothing more. The newer `main` commit was deliberately **not** merged
into this branch.

---

## 3. Architecture

```
frontend (React 18 + Vite 6, JavaScript/JSX, Arabic RTL)
    │  fetch  /api/v1/...   (Bearer JWT on /api/v1/admin/* and /auth/me)
    ▼
backend (FastAPI — focused modular monolith)
    ├── api/deps.py           session, current admin, super-admin guard, pagination
    ├── api/v1/endpoints/     routing + Pydantic request/response schemas
    ├── services/             pricing, orders, catalog, audit, slugs, store settings
    ├── models/               SQLAlchemy 2.x ORM
    ├── storage/              provider interface; local active, R2 adapter inert
    └── db/                   engine/session; Alembic owns the schema
    ▼
SQLite (local dev + tests)  →  MySQL 8 later via DATABASE_URL, same models
```

Full detail is now in the documentation set, not in this file:
[backend-architecture.md](backend-architecture.md),
[frontend-architecture.md](frontend-architecture.md),
[database-model.md](database-model.md), [api-modules.md](api-modules.md).

---

## 4. Work completed in the continuation session

### 4.1 The two failing frontend tests — fixed (`1651ce0`)

Both were ambiguous Testing Library queries in the **test files**. No application code was
changed.

- `storefront.test.jsx` — `getByText("200 ₪")` was ambiguous because a 2 × 100 ₪ cart
  legitimately renders that string **three** times: the cart line total, the summary
  subtotal, and the summary total (delivery is only priced at checkout). Now scoped: the
  line via its remove control, and the subtotal and total via their labelled rows inside
  the `complementary` landmark.
- `admin.test.jsx` — `getByText("بانتظار المراجعة")` matched both the row status badge and
  an `<option>` in the status filter. Now scoped with
  `within(screen.getByRole("table"))`.

The assertions were **narrowed, not weakened**: each now pins which element carries the
value. Result: **24 passed, 0 failed**.

### 4.2 A real configuration defect — found and fixed (`46bb057`)

Following the documented setup (`copy .env.example .env`) crashed **every** entry point —
Alembic, the seed and the application:

```
SettingsError: error parsing value for field "CORS_ORIGINS" from source "DotEnvSettingsSource"
```

pydantic-settings JSON-decodes complex (list) fields inside the env/dotenv source, before
field validators run, so the existing `mode="before"` splitter never saw the
comma-separated value that `.env.example` documents. The documented setup path was
therefore broken for anyone starting from scratch.

Fixed by annotating the field with `NoDecode` (available in the already-declared
`pydantic-settings>=2.6`) so the raw string reaches the validator, which now also accepts a
JSON list.

The pre-existing test passed `CORS_ORIGINS` as a keyword argument, which bypasses the
dotenv source entirely and so could never have caught this. Four regression tests were
added that load from a real `.env` file, from an environment variable, from a JSON list,
and one asserting the shipped `.env.example` parses unedited.

This was found only because the end-to-end run actually followed the documented setup.

### 4.3 Local end-to-end smoke run — performed, 27/27 checks passed

Run over **real HTTP** against a live Uvicorn instance with a seeded SQLite database, not
through the test client. The full documented flow:

```
[PASS]  1. GET /health returns 200
[PASS]  2. admin login issues a bearer token
[PASS]  3. GET /auth/me returns the signed-in admin
[PASS]  4. admin route rejects an unauthenticated caller (401)
[PASS]  5. public categories are listed
[PASS]  6. admin creates a product (HTTP 201)
[PASS]  7. the new product is visible on the storefront
[PASS]  8. the new product is findable by search
[PASS]  9. public delivery areas are listed
[PASS] 10. server prices the cart from its own data (subtotal 300, delivery 20, total 320)
[PASS] 11. compare_at_price is not charged (unit 150, compare_at 200)
[PASS] 12. guest checkout creates an order (ORD-260801-5398)
[PASS] 13. order total matches the server-priced total
[PASS] 14. order lookup without a token is refused
[PASS] 15. order lookup with the token succeeds
[PASS] 16. stock decremented by the ordered quantity (10 -> 8)
[PASS] 17. the order appears in /admin/orders
[PASS] 18. admin changes the order status (pending -> confirmed)
[PASS] 19. the status change is recorded in history with the acting admin
[PASS] 20. admin uploads an image to local media storage
[PASS] 21. the uploaded image is served over HTTP
[PASS] 22. the image is attached to the product
[PASS] 23. the storefront serves the product with its image
[PASS] 24. a real coupon validates server-side
[PASS] 25. an invalid coupon is rejected (HTTP 400)
[PASS] 26. admin actions are written to the audit log
[PASS] 27. public store settings exclude private fields
```

The script was a throwaway operator script in a scratch directory; it is **not** committed
and is not part of the test suite.

**Frontend ↔ backend wiring** was verified separately through the real Vite dev server and
its shipped proxy configuration:

| Path | Result |
| --- | --- |
| `/` and deep links `/product/:slug`, `/cart`, `/admin/orders`, `/track-order` | 200, SPA entry served |
| `/health` | 200 |
| `/api/v1/store/settings`, `/products`, `/categories` | 200 |
| `/media/seed-hero-teal.png` | 200, `image/png`, 20003 bytes |
| `/api/v1/admin/dashboard` without / with a token | 401 / 200 |

**No browser verification was performed** — no browser tooling was available in the
session. Nothing has been visually inspected. See §11.

### 4.4 Deployment templates — written (`b0a0049`)

`deployment/` previously held only a `.gitkeep`.

```
deployment/README.md                                     placeholders, naming, checklist
deployment/systemd/commerce-CLIENT_SLUG.service.example
deployment/nginx/commerce-CLIENT_SLUG.conf.example
deployment/env/backend.env.example
```

Only the four approved placeholders appear — `CLIENT_SLUG`, `CLIENT_DOMAIN`,
`BACKEND_PORT`, `PROJECT_PATH` — verified by grep. No real domain, path, client name or
secret. Every file states that it is an example that has never been installed or run on a
server. Nothing was deployed or activated.

### 4.5 Documentation — written (`37680ac`)

The root `README.md` was rewritten and thirteen `docs/` pages added, listed in §9. Facts
were taken from the running system — the live OpenAPI schema, `Base.metadata`, the route
tables — rather than from the previous handoff. That is how the table count was corrected
from 21 to **23**.

---

## 5. Verification results (all fresh, end of session)

| Check | Command | Result |
| --- | --- | --- |
| Dependency install | `pip install -e ".[dev]"` | succeeded |
| Backend tests | `python -m pytest` | **74 passed**, 1 warning, 63.35 s |
| Backend coverage | `python -m pytest --cov=app --cov-report=xml` | **TOTAL 88 %** (2867 statements, 351 missed); `coverage.xml` written |
| Alembic, clean database | `alembic upgrade head` on a new `verify_clean.db` | `-> 0001_initial`, then `0001_initial (head)`; 23 app tables + `alembic_version` |
| Seed idempotency | `scripts.seed` run repeatedly on the clean database | **identical row counts across all 24 tables**, compared programmatically, not by eye |
| App import + health | `TestClient(app).get("/health")` | `200 {'status': 'ok', 'app': 'Commerce Template', 'environment': 'development'}` |
| OpenAPI generation | `app.openapi()` | **62 paths**, 98 component schemas |
| Frontend install | `npm ci` | succeeded |
| Frontend tests | `npx vitest run` | **24 passed, 0 failed** (2 files) |
| Frontend build | `npm run build` | `✓ 85 modules transformed`, `index-mBIjAind.js 384.59 kB` (gzip 105.77 kB), `index-DK8Trf84.css 4.53 kB`, built in 4.65 s |
| Frontend dependencies | `npm ls --depth=0` | clean, 10 direct dependencies |
| Whitespace | `git diff --check` | clean |
| Tracked-file hygiene | `git ls-files` filtered | no `node_modules`, `dist`, `*.db`, real `.env`, venv, coverage or egg-info; the only `uploads` path is the intentional `.gitkeep` |
| Typecheck | — | **not configured** (JavaScript by design; no `tsconfig`, and none should be added) |
| Lint | — | **not configured** (no ESLint in `frontend/`, no Ruff/mypy in `backend/`) |

Seed output on a clean database:

```
artwork: 13 placeholder images   categories: 15        products: 31
variants: 9                      package contents: 8   hero slides: 3
banners: 3                       home sections: 8      coupons: 2
delivery areas: 5                articles: 4           static pages: 6
demo order: ORD-260801-3354      admin: skipped (no credentials supplied)
```

---

## 6. Backend surface

**62 paths**, `/health` outside the `/api/v1` prefix: 23 public, 2 auth, 37 admin. The full
list is in [api-modules.md](api-modules.md).

Uniform error shape `{"error": {"code": "...", "message": "...", ...}}`, produced by three
exception handlers in `app/main.py`.

---

## 7. Database

**23 application tables**, all created by the single revision `0001_initial`. The previous
handoff said 21; the correct count was confirmed from `Base.metadata` and from a freshly
migrated database.

```
admin_users        articles          audit_logs        banners
categories         coupons           delivery_areas    hero_slides
home_sections      media_assets      order_items       order_status_history
orders             package_items     product_images    product_option_values
product_options    product_specifications              product_variant_option_values
product_variants   products          static_pages      store_settings
```

`tests/test_migrations.py` asserts the migrated schema and `Base.metadata` match, so a
drifting model is a test failure. Details in [database-model.md](database-model.md).

---

## 8. Feature status

| Area | Status |
| --- | --- |
| Authentication | complete — Argon2 + PyJWT HS256; deactivating an admin invalidates its token on the next request |
| Roles | complete — `super_admin` / `admin`, with self-protection rules enforced in the service layer |
| Media storage | complete (local) — magic-byte validation, size limit, random stored names; R2 is an inert boundary |
| Orders | complete — guest checkout, `ORD-YYMMDD-NNNN`, immutable item snapshots, status history, token-scoped lookup |
| Inventory | complete — decremented once at creation, restored once on cancellation |
| Coupons | complete — percentage/fixed, min order, cap, usage limit, date window |
| Delivery | complete — per-area fee, minimum, free-delivery threshold |
| Content | complete — hero slides, banners, home sections, articles, static pages |
| Settings | complete — single row, private fields excluded from the public projection |
| Pricing | complete — server-authoritative; no endpoint accepts a client-supplied price |
| Audit log | complete — credentials and tokens stripped |
| Storefront | complete — every commercial value comes from the API |
| Admin workspace | complete — all screens listed in [admin-capabilities.md](admin-capabilities.md) |
| Deployment templates | complete as **inactive examples**, never installed |
| Documentation | complete |

---

## 9. Documentation set

```
README.md                        rewritten
docs/local-setup.md              docs/backend-architecture.md
docs/frontend-architecture.md    docs/database-model.md
docs/api-modules.md              docs/admin-capabilities.md
docs/sqlite-workflow.md          docs/future-mysql-migration.md
docs/future-r2-integration.md    docs/deployment-templates.md
docs/new-client-checklist.md     docs/backup-and-restore.md
docs/known-limitations.md
```

---

## 10. Partially implemented (documented, not defects)

1. **Recently-viewed products** — fetched one slug at a time; a batch endpoint would be
   better.
2. **Home showcase backgrounds** — fixed gradients, not admin-editable.
3. **Search** — normalised `LIKE` over `Product.search_text`; correct, but not a full-text
   index.
4. **R2 storage** — interface boundary only; `save()` and `delete()` raise.
   *Superseded 2026-08-02:* implemented on `feat/vista-preview-data-storage`, unit-tested
   against a stub, **never run against a real bucket**. See the top of this file.

`maintenance_mode` was the fifth entry here. It is complete as of 0.3.0-rc.1 — backend
gate, Arabic RTL storefront screen, and tests at both layers.

---

## 11. Not done, and deliberately so

1. **Browser verification beyond Chrome** — the 0.3.0-rc.1 pass opened every public and
   admin route in real Chrome 151 at 390 / 768 / 1440 px and fixed two mobile layout
   defects ([acceptance/visual-qa.md](acceptance/visual-qa.md)). Firefox, WebKit, physical
   devices and a visual-regression baseline are still missing.
2. **MySQL in production** — proven in CI against an ephemeral MySQL 8 service on every
   relevant push, never on a real server. See
   [future-mysql-migration.md](future-mysql-migration.md).
3. **Deployment** — templates written; nothing installed, activated or executed anywhere.
4. **React Router advisory** — `react-router-dom` 6.30.4 carries an open-redirect/XSS
   advisory with **no fix inside v6**; the only remedy is a breaking v7 upgrade. Not taken,
   deliberately. Current exposure assessed as low. Reasoning in
   [known-limitations.md](known-limitations.md).
5. **Product scope exclusions** — no customer accounts, no card payments, no
   multi-tenancy, no reviews, no email sending.

---

## 12. Architectural decisions that must not change without a stated reason

1. **The frontend stays JavaScript/JSX.** No TypeScript. Nothing may be imported from
   `feat/frontend-foundation`.
2. **The design is preserved.** Presentational components receive one flat `v` view-model.
3. **`utils/A.jsx`** renders a router `<Link>` for internal paths and a plain `<a>` for
   external schemes. Not a global click interceptor.
4. **The server owns every number.** Client-supplied totals are ignored.
5. **`compare_at_price` is never charged.**
6. **Alembic is the schema of record.** `create_all` builds only throwaway test databases.
7. **No fabricated data.** No invented ratings or reviews; the contact form opens a real
   WhatsApp message.
8. **No customer accounts.** Guest checkout only.
9. **Order confirmation is token-scoped** via `Order.public_token` in `sessionStorage`.
10. **Images fall back to the design's tone gradients.** Media is never Base64 or BLOB.
11. **One instance per client.** No multi-tenancy.
12. **No card payments.**
13. **The generic `uploads/` ignore rule stays removed** from `.gitignore` — a
    parent-level directory ignore would make `backend/data/uploads/.gitkeep` untrackable.

---

## 13. Runtime files that must remain untracked

Present on disk, correctly ignored, verified not tracked:

```
backend/.venv/                      backend/data/commerce_dev.db
backend/data/uploads/*              (only .gitkeep is tracked)
backend/coverage.xml, .coverage     backend/**/__pycache__/, *.egg-info
frontend/node_modules/              frontend/dist/
.env, .env.*  (except .env.example)
```

`backend/.env` exists locally and is correctly ignored — confirmed with
`git check-ignore -v`.

---

## 14. Protected-scope confirmations

- **`main`**: not modified. It was **already** at `0c6ff5d` when the continuation session
  began — the previous handoff's record of `2c418a4` was stale. The session read its hash
  and nothing else. Nothing was committed, merged or pushed to it, and the newer `main`
  commit was deliberately not merged into this branch.
- **`feat/frontend-foundation`**: not modified. Still at `f2ddd6e`. Never checked out,
  merged, rebased or read from. The abandoned TypeScript migration was not reused.
- **`bbaa7f7`**: not amended, rebased or force-pushed. All new work sits on top of it.
- **`D:\Project\MALIK`**: not accessed. No file in it was read, written, copied from or
  executed. Every command was anchored to `D:\Project\commerce-template`.
- **Production systems**: none accessed. No SSH, no production server, no real MySQL, no
  Nginx, no systemd, no Redis, no Cloudflare. The only database used was local SQLite; the
  only network access was `pip install`, `npm ci`/`npm audit` from the public registries,
  and HTTP to `127.0.0.1` / `localhost`.
- **No client branding** in tracked content. The only `MALIK` occurrences are the
  scope-prohibition sentences in this file and in `continuation-prompt.md` — guardrails,
  not branding.

---

## 15. If work continues

Items 1, 3 and 5 of the previous list — browser verification, gating on
`maintenance_mode`, and exercising MySQL — were done in the 0.3.0-rc.1 acceptance pass.
What remains, in order of value:

1. **Add rate limiting to `/api/v1/auth/login`** before any public deployment. Nothing in
   the application or the Nginx template does this today.
2. **Decide on the React Router v7 upgrade** — see §11 item 4.
3. **Add ESLint and Ruff**, then extend CI to run both suites and both linters, not just
   the MySQL gate.
4. **Widen browser coverage** past Chrome, and keep a visual-regression baseline so a
   future change cannot break the design silently.
5. **Take a first client instance to a real server** and work through the operational half
   of [future-mysql-migration.md](future-mysql-migration.md) — charset, users, privileges,
   backups, pooling.

Reproduction commands for the current state are in
[local-setup.md](local-setup.md) and [sqlite-workflow.md](sqlite-workflow.md).
