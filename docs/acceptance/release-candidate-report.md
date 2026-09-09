# Release-candidate report — 0.3.0-rc.1

> **HISTORICAL / SUPERSEDED:** This records an earlier acceptance run and is not the
> current production-readiness source.

Branch `feat/template-acceptance-rc`, cut from `feat/template-productization` at
`2ed239b`. This is an acceptance pass over an existing implementation, not a rebuild.

Every figure below came from a command run in this session. Nothing is carried over from
an earlier handoff, and nothing is asserted that was not observed.

---

## 1. Gate matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Clean SQLite instance | **PASS** | 35/35 HTTP checks against a live Uvicorn on a temporary database — §2 |
| Profile validation | **PASS** | `validate` exit 0 on a customised profile; exit 2 with a field-named message on a bad one — §3 |
| Bootstrap idempotency | **PASS** | second and third `apply` create nothing and preserve owner edits — §2.4 |
| Admin creation and login | **PASS** | `app.initial_data` then a real bearer token over HTTP |
| Catalog management | **PASS** | category, standard product, two specifications, inventory |
| Media | **PASS** | upload, served over HTTP as `image/png`, attached, visible on the storefront |
| Guest checkout | **PASS** | server-priced 300 + 20 = 320; client-supplied totals impossible |
| Orders and inventory | **PASS** | stock 10 → 8, decremented once; order in Admin; status change recorded in history |
| Maintenance mode | **PASS** | implemented this session, backend + frontend, 9 backend and 5 frontend tests — §4 |
| Backend tests | **PASS** | **149 passed**, 1 warning, 38.5 s; **90 %** coverage (3249 statements, 335 missed) |
| Frontend tests | **PASS** | **29 passed**, 3 files |
| Frontend build | **PASS** | 86 modules, `index-*.js` 387.44 kB (gzip 106.49 kB), built in 2.29 s |
| Visual acceptance | **PASS** | real Chrome 151 at 390 / 768 / 1440; 78 route × viewport passes, 11 interaction passes, **3 defects found and fixed** — §5 |
| MySQL CI | **PASS** | ephemeral MySQL 8 service in GitHub Actions; runs #2 and #3 both `success`, every step green — §6 |
| Secret and tracked-runtime-file scan | **PASS** | 190/190 tracked files scanned, 0 real findings — §7 |

**Every mandatory gate is verified.** The tag `v0.3.0-rc.1` is therefore created.

---

## 2. Clean-instance acceptance

A disposable instance built from nothing, in the operator's scratch directory — never
`commerce_dev.db`, and no developer file was touched:

- a temporary SQLite database
- a temporary uploads directory
- an untracked temporary environment file, loaded as process environment variables so it
  overrides the developer's `backend/.env`
- a copy of `instance/client-profile.example.yaml`, customised (`acceptance-store`)
- admin credentials supplied only as command-line arguments

The real lifecycle ran in order: `alembic upgrade head` → `validate` → `plan` → `apply` →
`manifest` → `app.initial_data` → Uvicorn → Vite.

### 2.1 Bootstrap creates a store, not a demo

| Check | Result |
| --- | --- |
| Products created by bootstrap | 0 |
| Orders created by bootstrap | 0 |
| Coupons created by bootstrap | 0 |
| Categories created by bootstrap | 0 |
| Admin accounts created by bootstrap | 0 — the only account is the one `app.initial_data` created |
| Store identity | from the profile: name, currency `ILS`, phone, `#1F4E4A` |
| Structure | the profile's 7 home sections and 6 static pages, and nothing else |
| Public settings projection | no `order_notifications_email`, no `id` |
| Manifest | no secret, no `SECRET_KEY`, no admin password, no `DATABASE_URL` |

### 2.2 Catalog, media and the storefront

Category → standard product (150 ₪, `compare_at` 200 ₪, stock 10, two specifications) →
PNG uploaded through Admin, served over HTTP as `image/png`, attached as primary. The
product then appeared through the public API with its image and specifications, the public
projection hid `cost_price`, the storefront served its deep link, and the Vite proxy served
the uploaded image.

### 2.3 Checkout, orders and inventory

| Check | Result |
| --- | --- |
| Server-priced cart | subtotal 300.00, delivery 20.00, total 320.00 |
| `compare_at_price` charged | never — unit price 150.00 |
| Guest checkout | HTTP 201, order created |
| Order total | 320.00, equal to the server-priced total |
| Inventory | 10 → 8, decremented exactly once |
| Order lookup without a token | refused |
| Order lookup with the token | 200 |
| Order in Admin | listed |
| Status change | pending → confirmed, recorded in history with the acting admin id |

### 2.4 Re-bootstrap, conflict and a second instance

| Check | Result |
| --- | --- |
| Owner edits StoreSettings through Admin | store name, announcement and phone changed |
| `apply` run again | succeeds; reports only `skip` and `update`, never `create` |
| Owner-edited settings after re-bootstrap | preserved exactly |
| Owner content after re-bootstrap | 6 pages → 6, 7 sections → 7; nothing duplicated or overwritten |
| Catalog and orders after re-bootstrap | untouched |
| Conflicting instance slug — `plan` | exit 3, reports the conflict |
| Conflicting instance slug — `apply` | exit 3, "Nothing was written" |
| Instance slug after the refused apply | unchanged |
| A second profile on a second temporary database | migrates, bootstraps, records its own slug and profile hash |
| The first instance afterwards | still serving its own data |

**35/35 then 17/17 checks passed.** Disposable runtime files were removed afterwards;
nothing that existed before the session was deleted.

---

## 3. A real defect found by acceptance

`ContactProfile.email` was validated as a plain string, but bootstrap writes it into
`StoreSettings` and `StoreSettingsPublic.email` is an `EmailStr`. A profile carrying an
address that `email-validator` rejects — a reserved TLD such as `.test`, or anything
malformed — passed `validate`, applied cleanly, and then made
`GET /api/v1/store/settings` return **500**. That endpoint is the storefront's first call,
so the shop was dead on arrival with no obvious cause.

The profile now uses the same `EmailStr`, so `commerce-instance validate` refuses it up
front with exit 2 and a message naming `contact.email`. Six regression tests cover it.

This was found only because acceptance created a genuinely new instance from a genuinely
new profile.

---

## 4. Maintenance mode

Previously stored, editable and published, with nothing acting on it.

**Backend** — `require_storefront_open` closes the public catalog, checkout and editorial
routers with `503 maintenance_mode`. Store identity moved to its own ungated router because
the maintenance screen is rendered from it.

**Frontend** — `StorefrontLayout` renders an Arabic RTL maintenance screen in place of the
storefront, built only from the public settings projection.

| Required behaviour | Verified |
| --- | --- |
| Disabled: public behaviour unchanged | ✅ backend test + browser sweep |
| Enabled: Arabic RTL maintenance screen on public routes | ✅ browser, 390/768/1440 |
| Uses store identity and safe contact information | ✅ name, tagline, WhatsApp, phone, email, hours |
| Admin login and protected admin routes reachable | ✅ backend test + browser |
| Admin APIs reachable to authenticated administrators | ✅ dashboard, products, settings all 200 |
| `/health` reachable | ✅ |
| No redirect loop | ✅ nothing redirects; the screen replaces the layout in place |
| No exposure of private settings | ✅ the public projection only |
| Disabling restores the storefront without rebuilding | ✅ the next request is served again |

Tests: 9 backend (`tests/test_maintenance_mode.py`), 5 frontend
(`src/test/maintenance.test.jsx`), plus 5 live-HTTP checks in the acceptance run.

---

## 5. Visual acceptance

Browser tooling **was** available: Chrome 151 was already installed and Node 25 ships a
global `WebSocket`, so the DevTools Protocol was driven directly. No browser-testing stack
was installed and none was added to `package.json`.

23 routes × 3 viewports, plus 3 maintenance routes × 3 viewports, plus 11 real
interactions. Full record, route by route:
[visual-qa.md](visual-qa.md).

Three defects found and fixed:

1. **The cart's order summary sat in an off-canvas column.** `grid-column:1`/`2` fought
   `--shop`, which collapses to one column below 900 px; 118 px of the summary — most of
   the checkout button — was clipped and unreachable on a phone. The same declarations
   inverted the desktop layout.
2. **A long store name pushed the cart button off the mobile header** by 7 px, on every
   public route at 390 px. The store name is client data, so this would hit real clients.
3. **`index.html` shipped a previous client's title and monogram favicon**, and the admin
   workspace never overrode the title.

All three are re-verified: 0 px overflow everywhere, at every width.

---

## 6. MySQL CI gate

`.github/workflows/mysql-compatibility.yml`. An **ephemeral MySQL 8 service container**
inside the GitHub Actions runner: created for the job, destroyed with it. It never reaches
this machine, the VPS or any production database, and its credentials are defined only in
the workflow. Local development stays on SQLite; Docker did not become a local requirement.

The gate verifies, against a real MySQL 8:

| Requirement | Where |
| --- | --- |
| Backend dependencies install | workflow step |
| MySQL service becomes healthy | `mysqladmin ping` loop, fails the job after 40 attempts |
| Alembic upgrades a new empty database to head | workflow step, plus a test asserting the stamped revision is head |
| The migrated schema matches the models | `test_the_migrated_schema_matches_the_models` |
| Tables are InnoDB and utf8mb4 | `test_tables_are_innodb_utf8mb4` |
| Profile validate, plan and apply succeed | `test_the_full_client_lifecycle_on_mysql` |
| Repeated apply is idempotent | same test — no `create`, and row counts unchanged |
| Instance metadata is recorded | `test_instance_metadata_is_recorded_and_manifest_has_no_secrets` |
| Manifest contains no secrets | same test, including the live `DATABASE_URL` |
| A conflicting slug is refused | `test_a_conflicting_instance_slug_is_refused` |
| Demo seed succeeds twice without uncontrolled duplicates | `test_the_demo_seed_is_idempotent_on_mysql` — all 24 table counts compared |
| Admin creation and login | `test_the_initial_admin_command_works_on_mysql` |
| Category and product persistence | `test_category_and_product_persist_through_the_api` |
| Decimal prices round-trip | `test_decimal_prices_round_trip_exactly` |
| JSON configuration fields round-trip | `test_json_configuration_fields_round_trip` |
| Foreign keys and unique constraints | `test_foreign_keys_are_enforced`, `test_unique_constraints_are_enforced`, `test_a_deleted_category_nulls_the_product_reference` |
| Guest order creation and inventory update | `test_guest_order_creation_and_inventory_update` |
| The SQLite suite still passes unchanged | workflow step |
| No runtime artefact is tracked | workflow step |

`tests_mysql/` is a separate directory outside `testpaths`, so the SQLite suite is
untouched and a normal `pytest` run never collects it.

**Observed, not assumed.** `gh` is not installed and the repository is private, so the run
was read through the GitHub REST API using the credential git already holds for this
remote.

- Run #1 — `failure`. Thirteen of fifteen tests passed; the two failures were in the test
  fixtures, which signed in with a reserved `.test` TLD. The same trap as §3, this time in
  the test code, not the product's.
- Run #2 — **`success`**, all twelve steps green.
- Run #3, on the release-candidate commit — **`success`**, all twelve steps green:
  containers initialised, dependencies installed, MySQL healthy, databases created,
  offline portability check, Alembic upgrade to head, MySQL integration suite, the SQLite
  suite unchanged, and the tracked-artefact check.

The tag points at a commit whose only difference from the run #3 tree is documentation;
`backend/`, `instance/`, `VERSION` and the workflow — every path the gate covers — are
byte-identical.

---

## 7. Repository hygiene

| Check | Result |
| --- | --- |
| `git diff --check` | clean |
| Working tree | clean |
| Tracked files | 190 |
| Tracked runtime artefacts | none — no `.env`, `*.db`, `node_modules/`, `dist/`, `.venv/`, `coverage.xml`, egg-info or `__pycache__` |
| `uploads` paths tracked | only the intentional `backend/data/uploads/.gitkeep` |
| Secret scan | 190/190 tracked files scanned against 7 patterns; 11 candidates, all reviewed, **0 real secrets** — every hit is a variable name (`token = ...`), a parameter declaration, a documented placeholder, or a deliberately fake URL inside a test that asserts such a value is rejected |

---

## 8. Protected scope

Nothing outside this repository was read, written or contacted.

- `D:\Project\MALIK` — never accessed.
- No SSH, no production server, no production database, no Nginx, no systemd, no Redis, no
  Cloudflare or R2 account, no other client project.
- **The local MySQL installation was not connected to.** A listener on port 3306 was
  observed while checking port availability and was deliberately left alone; the only MySQL
  connection in this work is the ephemeral GitHub Actions service container.
- Nothing was deployed.
- The storefront and Admin were not redesigned. The three visual fixes restore the existing
  design's intent at widths where it was broken; no colour, type scale, spacing token or
  layout concept was reinterpreted.

Protected branches, unchanged and unmerged:

```
main                            0c6ff5decdfa0d84b5db5bce95e6cf7c1a60a276
feat/frontend-foundation        f2ddd6eb3126f229e5c34dc80a3c0857440b6d54
feat/fullstack-commerce-mvp     8260e323ad6125b2e2bfcfb7b6407cd4955c55f3
feat/template-productization    2ed239b2ffb4eae59863f1fcca3eae2965541926
```

No branch was merged. All work is on `feat/template-acceptance-rc`.

---

## 9. What a release candidate still does not mean

- **Nothing has been deployed.** The deployment templates remain examples that have never
  been installed or run.
- **MySQL is proven in CI, not in production.** Charset choices, users, privileges,
  backups and pooling on a real server are still open — see
  [../future-mysql-migration.md](../future-mysql-migration.md).
- **One browser engine.** Chrome only; no Firefox, no WebKit, no physical device, and no
  visual-regression baseline, so a future change can still break the design silently.
- **No rate limiting on `/api/v1/auth/login`.** Add it before any public launch.
- **`react-router-dom` 6.30.4** still carries the advisory with no fix inside v6; the v7
  upgrade was deliberately not taken. See [../known-limitations.md](../known-limitations.md).
- **No lint or typecheck** is configured in either half of the repository.
