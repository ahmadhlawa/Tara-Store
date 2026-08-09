# Known limitations

An honest list of what this application does not do, does only partly, or has not proven.
Read it before promising anything to the client.

## Vista Store — specific to this instance

- **The store cannot take a real order.** No delivery area exists, and checkout requires
  one. No catalog, no phone number, no address. All of it is waiting on the owner —
  `docs/client/data-needed-from-owner.md`.
- **Business data is unverified except the name.** The supplied Facebook page is
  login-walled; only "Vista Store / متجر فيستا" is confirmed. Currency, colours and
  timezone are template defaults carried over, not Vista Store values.
- **No visual QA has been done.** No browser tooling was available. Every screen renders
  in jsdom and the print CSS is asserted, but nothing has been *looked at* — including the
  printed A4 invoice and the cancelled watermark. See `docs/client/local-acceptance.md`.
- **No deployment target is confirmed.** Whether a FastAPI app runs on the client's cPanel
  account is unanswered. See `docs/deployment/cpanel-capability-checklist.md`.

## Invoicing — what it does not do

- **No server-side PDF.** Printing is the browser's, via `window.print()` and Save-as-PDF.
  Nothing generates or emails a PDF file, because the hosting environment's capabilities
  are unknown.
- **No reissue and no credit note.** An invoice is issued once and either stands or is
  cancelled. A cancelled order cannot be reconfirmed, so it never produces a second
  invoice. Correcting an invoice means cancelling the order and placing a new one.
- **No backfill.** Orders confirmed before migration `0003` have no invoice, and none is
  created retroactively — an invoice snapshots the store as it was on the issue date, and
  that state no longer exists.
- **Tax is a single flat rate** on the order total, applied to goods and delivery
  together. There are no per-product tax classes and no exemptions. It is off by default,
  and the instance is **not** a tax invoice issuer until the owner says so in writing.
- **Numbering is one global series per prefix.** No per-year reset, no per-branch series.
  Changing the prefix after invoices exist leaves two series in the same ledger.

## Deliberately out of scope

These are decisions, not gaps. Adding any of them is a change of product, not a bug fix.

- **No customer accounts.** Guest checkout only. There is no registration, no login, no
  order history for shoppers, no saved addresses.
- **No online card payment.** `cash_on_delivery` and `manual` only. There are no card
  fields anywhere in the schema, the API or the UI, and no payment gateway integration.
- **No multi-tenancy.** One instance per client. No `tenant_id`, no shared database, no
  SaaS control plane.
- **No product reviews or ratings.** There is no review entity, so no star ratings are
  displayed. The rating row is gated behind a flag that is currently always false, and the
  product page has no reviews tab. Nothing invents this data.
- **No email sending.** `order_notifications_email` is stored but nothing sends to it. No
  order confirmation email, no password reset email.
- **No shipping-carrier integration**, no live rates, no tracking numbers. Delivery is a
  flat per-area fee.

## Partly implemented

- **Recently-viewed products** are fetched one slug at a time (`Promise.allSettled` over up
  to six requests). Correct, but a batch endpoint would be better.
- **Home showcase blocks** use fixed gradient backgrounds. Which sections appear is
  admin-controlled; the background is not yet editable.
- **Search** is a normalised `LIKE` over `Product.search_text`. It tolerates spelling and
  diacritic variation and is correct, but it is not a full-text index and will not scale.
- **Cloudflare R2 storage** is implemented but has never touched a real bucket. `save()`,
  `delete()`, `exists()` and prefix containment are written and unit-tested against a stub
  S3 client; no credentials have ever been available here, so the live smoke test is
  **blocked, not passed**. Local disk remains the default and the only provider proven end
  to end. See [deployment/r2-preview-setup.md](deployment/r2-preview-setup.md).

## Not verified

Be precise about these when reporting status.

- **Browser verification covers Chrome only.** Every public and admin route was opened in
  real Chrome 151 at 390 / 768 / 1440 px during the 0.3.0-rc.1 acceptance pass, and two
  mobile layout defects were found and fixed —
  [acceptance/visual-qa.md](acceptance/visual-qa.md). Firefox, Safari/WebKit and physical
  devices remain untested, and no visual-regression baseline is kept, so a future change
  can still break the design silently.
- **MySQL is proven in CI, not in production.** `.github/workflows/mysql-compatibility.yml`
  runs the migration, the client lifecycle, the demo seed and focused integration tests
  against an ephemeral MySQL 8 service on every relevant push. No MySQL server outside CI
  has ever been contacted, and nothing has been deployed. An isolated local development
  container is now configured in `compose.mysql.dev.yml`, but **it has never been run** —
  Docker is not installed on the machine this was written on. See
  [future-mysql-migration.md](future-mysql-migration.md) and
  [deployment/mysql-local-development.md](deployment/mysql-local-development.md).
- **The preview catalog is demonstration content, not Vista Store's.** Every product name
  and price in `instance/preview/vista-social-preview.yaml` is invented. It is removable
  with `vista-preview purge --confirm`. See
  [client/preview-content-manifest.md](client/preview-content-manifest.md).
- **The preview catalog has never been looked at in a browser.** No browser tooling was
  available. See [client/preview-visual-qa.md](client/preview-visual-qa.md).
- **The deployment templates have never been installed or run** on any server. They are
  reviewed examples, not proven configuration.
- **Python 3.13 is what the development environment runs**, while the code targets 3.12+.
  Nothing has failed, but the deployment target should pin a version explicitly.

## Operational gaps

- **No rate limiting on `/api/v1/auth/login`.** The application does not implement it and
  the Nginx template does not configure it. Add `limit_req` before a public launch.
- **No password reset flow.** A locked-out administrator needs another super admin, or a
  command-line reset. There is no email-based recovery.
- **No refresh tokens.** An access token simply expires after
  `ACCESS_TOKEN_EXPIRE_MINUTES` and the administrator signs in again.
- **No structured logging or error tracking.** Output goes to the journal. There is no
  request id, no log aggregation, no Sentry-style reporting.
- **No health check beyond `/health`.** It confirms the process is up; it does not check
  the database or storage.
- **No automated backups.** The procedure is documented in
  [backup-and-restore.md](backup-and-restore.md); scheduling it is a deployment task.
- **`vite preview` is not a production server.** Deep links depend on the SPA fallback that
  Nginx provides.

## Behaviours that surprise people

- **`/track-order` only works in the browser that placed the order.** The `public_token`
  lives in `sessionStorage`; the order number alone never reveals an order. This is
  intentional, but customers will ask.
- **The seed resets seeded product stock on every run**, undoing stock movements from demo
  orders. Fine locally; never run it against a live store.
- **Deleting a media asset does not update products referencing its URL.** Those fall back
  to the design's gradient placeholder rather than erroring.
- **Deactivating an administrator invalidates their token immediately**, mid-session,
  because the account is re-read on every request.
- **Rotating `SECRET_KEY` signs every administrator out.** That is the intended mechanism,
  not a fault.
- **Arabic product names produce Arabic slugs.** Browsers percent-encode them
  automatically; command-line clients may need the URL encoded by hand.
- **The contact form opens a real WhatsApp message** rather than showing a fake "sent"
  confirmation, because there is no mail sending. The newsletter block is a call to action,
  not a subscription form.

## Dependency advisories

`npm audit` currently reports 7 advisories (5 moderate, 1 high, 1 critical). They split
into two very different groups.

**Development tooling only — not in the shipped bundle:** `vite`, `vite-node`, `esbuild`,
`vitest`, `@vitest/mocker`. These affect the dev server and the test runner. The
"critical" `vitest` entry requires the Vitest UI server to be listening, which this project
never starts. Nothing here reaches a deployed instance, since production serves the static
`dist/` output through Nginx.

**A production dependency — `react-router` / `react-router-dom` 6.30.4.** The advisories
are an open redirect via a backslash in `<Link>` / `useNavigate`, and an XSS following from
it. This one ships to users, so it deserves a clear answer:

- **There is no fix within v6.** The vulnerable range is `6.0.0 – 7.17.0`, and 6.30.4 is
  already the newest v6 release. `npm audit fix --force` resolves it by installing React
  Router **v7**, a breaking major upgrade.
- **It was deliberately not upgraded.** A v7 migration is a framework change well beyond
  this MVP's scope and would put the preserved design and the whole route layer at risk.
  That is a decision to take deliberately, not as a side effect of an audit fix.
- **Current exposure looks low.** Every `navigate()` call site uses a hard-coded literal
  path prefix; the only user-supplied value that reaches routing is the search term, which
  goes through `encodeURIComponent` into a query string, never into the path. `<Link to>`
  targets come from static navigation constants, server-generated slugs and ids, or
  admin-configured URLs — and `utils/A.jsx` sends anything matching `http(s):`, `tel:`,
  `mailto:` or `wa.me` to a plain `<a>` rather than to the router. No unauthenticated,
  user-controlled value reaches a router path today.

Re-check this before a public launch, and treat "upgrade to React Router v7" as its own
planned piece of work with its own regression testing. If a future change starts routing a
user-supplied path (a `returnTo` parameter, for instance), the upgrade stops being
optional.

## Quality tooling not configured

- No ESLint config in `frontend/`, and no Ruff or mypy config in `backend/`.
- No typecheck step — the frontend is JavaScript by design; no `tsconfig` exists and none
  should be added.
- No CI pipeline. Tests are run manually.
