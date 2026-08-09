# Changelog

Golden Template releases. The authoritative version lives in the `VERSION` file at the
repository root; nothing else declares it.

Instances record the template version they were initialized from in `instance_metadata`,
and report it through `commerce-instance manifest`.

## 0.3.0-rc.1 — 2026-08-01

Release candidate. An acceptance pass over the working implementation: a clean client
instance built from scratch and driven over real HTTP, maintenance mode completed, browser
acceptance in real Chrome, and an ephemeral MySQL 8 gate in CI. Full evidence in
[docs/acceptance/release-candidate-report.md](docs/acceptance/release-candidate-report.md).

### Added

- **Maintenance mode**, previously stored and editable but acted on by nothing.
  - Backend: `require_storefront_open` closes the public catalog, checkout and editorial
    routers with `503 maintenance_mode`. Store identity moved to its own ungated router,
    because the maintenance screen is rendered from it. `/health`, authentication and the
    whole admin surface stay open, so the owner can switch it back off; the storefront
    returns on the next request, with no rebuild and no restart. Nothing redirects, so
    there is no loop.
  - Frontend: an Arabic RTL maintenance screen replaces the storefront in place, built
    only from the public settings projection — store name, tagline and safe contact
    details. `/admin` is a separate route branch and never reaches it.
  - Tests: 9 backend, 5 frontend.
- **Ephemeral MySQL 8 CI gate** — `.github/workflows/mysql-compatibility.yml`, a GitHub
  Actions service container created for the job and destroyed with it. It proves, against
  a real MySQL 8: Alembic upgrades a new empty database to head, the migrated schema
  matches the models, every table is InnoDB/utf8mb4, profile validate/plan/apply succeed,
  a repeated apply is idempotent, instance metadata is recorded, the manifest carries no
  secrets, a conflicting slug is refused, the demo seed runs twice without changing a
  single row count, admin creation and login work, categories and products persist,
  `Decimal` money and JSON config round-trip exactly, and foreign keys, unique constraints
  and guest checkout with inventory all behave. `tests_mysql/` sits outside `testpaths`,
  so the SQLite suite is unchanged and a normal `pytest` run never collects it.
- **`mysql` optional dependency group** — `PyMySQL[rsa]`, which MySQL 8 needs for its
  default `caching_sha2_password` authentication. CI-and-deployment only; the SQLite
  development runtime is unaffected.
- **Acceptance documentation** — `docs/acceptance/release-candidate-report.md` (gate
  matrix) and `docs/acceptance/visual-qa.md` (every route, viewport and interaction).

### Fixed

- **A profile could produce a dead storefront.** `contact.email` was validated as a plain
  string, but bootstrap writes it into `StoreSettings` and `StoreSettingsPublic.email` is
  an `EmailStr`. A profile with a reserved-TLD or malformed address validated, applied
  cleanly, and then made `GET /api/v1/store/settings` return 500 — the storefront's first
  call. The profile now uses the same `EmailStr`, so `commerce-instance validate` refuses
  it up front with exit 2 and a message naming the field.
- **The cart's order summary was unreachable on a phone.** `grid-column:1`/`grid-column:2`
  fought `--shop`, which collapses to a single column below 900 px, so the summary landed
  in an implicit off-canvas column — 118 px of it, including most of the checkout button,
  clipped by the global `overflow-x:hidden`. The same declarations also inverted the
  desktop layout. Removed; auto-placement and the existing `order` now do the work.
- **A long store name broke the mobile header.** The logo block could not shrink, so a
  realistic client store name pushed the cart button 7 px off the edge at 390 px on every
  public route. It now shrinks and ellipsizes.
- **The template shipped a previous client's identity.** `index.html` carried that store's
  `<title>` and a monogram favicon, and the admin workspace never overrode the title. Both
  are neutral now, and `AdminLayout` sets its own.

### Notes

- No storefront or Admin redesign. The three visual fixes restore the existing design's
  intent at widths where it was broken; no colour, type scale, spacing token or layout
  concept changed.
- No deployment, and no MySQL server outside GitHub Actions was contacted. SQLite remains
  the local runtime, and Docker is not a local requirement.
- Backend 149 tests / 90 % coverage, frontend 29 tests, production build clean.

## 0.2.0 — 2026-08-01

Productization: the template can now create clean, independent store instances from a
validated non-secret profile, instead of relying on hand-editing a copy of the demo store.

### Added

- **`VERSION`** — one authoritative Golden Template version, read at runtime by
  `app.core.template_version`. A test asserts it is not hard-coded anywhere else.
- **Instance profiles** (`instance/`) — validated, non-secret YAML describing one store:
  identity, domain, locale, timezone, currency, contact defaults, theme colours, feature
  flags, home page structure and static page metadata.
  - `instance/client-profile.example.yaml` — annotated template to copy per client
  - `instance/demo-profile.yaml` — the demo store's identity
  - Rejects invalid slugs, unsupported schema versions, malformed colours, unknown feature
    flags, unknown keys and missing required values, with explicit messages.
  - Rejects credential-shaped keys at any depth. Secrets stay in environment variables.
- **`instance_metadata` table** and Alembic revision `0002_instance_metadata` — records
  instance slug, template version at initialization, profile schema version, profile hash,
  enabled features and bootstrap timestamps. Single row; no `tenant_id`, no multi-tenancy.
- **`commerce-instance` CLI** (`python -m scripts.instance_cli`):
  - `validate` — profile structure and semantics; touches no database
  - `plan` — deterministic create / skip / conflict preview; writes nothing
  - `apply` — idempotent client bootstrap; refuses a conflicting instance slug
  - `manifest` — non-secret JSON manifest, to stdout or a file
- **`commerce-mysql-check` CLI** (`python -m scripts.mysql_compat`) — offline MySQL
  portability check that connects to nothing. Covers table and index compilation, money
  columns, JSON columns, index key length under `utf8mb4`, foreign keys, unique
  constraints, enum-like columns and Alembic head availability.
- **Documentation** — `docs/client-lifecycle.md` (create, operate, upgrade, backup and
  restore, plus the future instance-factory design) and
  `docs/architecture/template-productization-design.md`.
- Runtime dependency: `PyYAML`.

### Changed

- **Two clearly separated initialization workflows.** The demo seed (`scripts.seed`) keeps
  its behaviour but is now explicitly labelled development-and-demonstration-only in its
  help text and module docstring. Client bootstrap (`commerce-instance apply`) creates
  store identity and structural defaults only — no products, orders, coupons or admin
  accounts — and never overwrites content edited through Admin.
- Admin creation remains the separate, explicit `python -m app.initial_data`.

### Notes

- No application behaviour, storefront design or Admin UI changed.
- SQLite remains the default local runtime. No MySQL server was contacted.
- The offline MySQL check is a compatibility signal, not proof of production readiness; an
  ephemeral MySQL integration test is still required before a first deployment.

## 0.1.0 — earlier

Full-stack commerce MVP: React/Vite storefront and admin workspace, FastAPI backend with
SQLAlchemy 2 and Alembic, local SQLite, admin authentication and roles, catalog, content,
media, guest checkout, orders, settings and audit logs.
