# Tara Store production templates

These are reviewable examples, not installed configuration. Repository maintenance
and release packaging do not deploy anything.

Production uses **MySQL for application data, Cloudflare R2 for media, a built static
SPA, and FastAPI under systemd behind Nginx**. LibreTranslate is the existing shared
private service at `http://127.0.0.1:5000`; application releases must not recreate,
upgrade, stop, or delete that service or its models.

## Files and isolation

- [Backend environment](env/backend.env.example): authoritative production settings.
- [Nginx site](nginx/commerce-CLIENT_SLUG.conf.example): SPA and loopback API proxy.
  `/media` is not served from disk; image URLs come from `R2_PUBLIC_BASE_URL`.
- [Systemd unit](systemd/commerce-CLIENT_SLUG.service.example): isolated backend process.
- [Template guide](../docs/deployment-templates.md): placeholders and review checks.

Replace `CLIENT_SLUG`, `CLIENT_DOMAIN`, `BACKEND_PORT` (an allocated unused loopback
port), and `PROJECT_PATH` (Tara's absolute application directory). Keep Tara's service
user, checkout, unit, site/logs, database/user, credentials and R2 objects separate
from other projects. Use `R2_OBJECT_PREFIX=tara-store/` and Tara-scoped bucket credentials.
The application's prefix guard does not replace storage permissions; prefer a
Tara-only bucket. Never replace shared server configuration or another project's unit.

## Preparation for a separately authorized deployment

1. Copy `deployment/env/backend.env.example` to untracked `backend/.env`. Fill the
   MySQL URL, generated `SECRET_KEY`, canonical origin and R2 blanks privately.
   URL-encode database passwords. Restrict the file to its service user (mode 600).
2. From `backend/`, install Python 3.12+ dependencies with
   `pip install -c constraints.txt ".[mysql,r2]"`. Both runtime extras are required.
   From `frontend/`, build with `npm ci` and `npm run build`.
3. Back up existing data before `alembic upgrade head`. Verify current/head;
   `0029_storefront_analytics` is the current repository head. Do not rewrite migrations or
   seed demo data into production.
4. Review substituted systemd/Nginx templates and certificate paths. Check the complete
   Nginx configuration before any separately authorized reload. Arrange Tara migration
   privileges with the operator; do not change shared MySQL global settings.
   See [MySQL notes](../docs/future-mysql-migration.md).
5. Verify `/health`, `/ready`, `/ar`, `/en`, locale deep links and Arabic Admin. Check
   direct R2 image URLs. `/ready` does not prove live R2 access. Verify translation
   connectivity without modifying the shared service.
6. Rehearse orders in an isolated disposable environment. Do not delete historical
   orders/invoices to clean up tests. Rehearse matched MySQL/R2 recovery using
   [backup and restore](../docs/backup-and-restore.md).
   For this prelaunch instance only, where all transactions are confirmed tests,
   use the separately guarded [transaction sanitizer](../docs/client-data-cutover.md#prelaunch-transaction-sanitation-separate-from-catalog-cutover).

Login throttling combines failed-attempt IP/account pairs with aggregate IP and
account budgets (five times `LOGIN_RATE_LIMIT`); a successful login clears only its
pair. Order create/lookup limits remain separate. These bounded in-memory budgets
are per process and reset on restart: the supplied unit runs one worker. Review
abuse controls before increasing workers; no shared caching infrastructure is added.
Nginx overwrites incoming forwarding headers with the actual peer address. If a
CDN/proxy is introduced, its trusted-IP handling requires an explicit operator review.
The SPA CSP allows its Google font stylesheet/font origins, inline styles and HTTPS
images; executable scripts stay same-origin. Hashed assets are immutable, HTML is
no-cache, and the same security headers apply to both.
Database engine logs/exception strings hide bound parameters, and R2 errors suppress
raw SDK exception chains. Password confirmation stays in the form and never reaches
the API. Keep protected environment files and privileged database access private.

SQLite, LocalStorageProvider, `backend/data/tara-uploads/`, local MySQL Compose,
preview/catalog tools and demo tooling remain development/test capabilities.
They are not production storage or instructions to copy customer runtime data.

## Tara analytics deployment gates

`ANALYTICS_RETENTION_DAYS=365` is an independent retention policy; do not treat it
as an AOP or proxy-trust setting. Keep `ANALYTICS_TRUST_CLOUDFLARE_HEADERS=false`
until origin authentication is fully enforced and verified.
Do not infer origin authenticity from CF headers alone. The Nginx template overwrites
`X-Tara-Analytics-Proxy`; replace its placeholder with a private random token of at
least 32 characters and put the identical value in the mode-600 backend `.env`.
Never commit either value. Keep the Nginx analytics limit in dry-run until actual
shared-IP traffic has been reviewed. Install the supplied prune service and timer;
check its first run and journal.

For custom-zone or per-hostname AOP, use this staged rollout only for Tara's vhost:

1. Generate and manage the custom client certificate and private key securely. Upload
   the leaf certificate and private key to Cloudflare. Install on the Nginx origin only
   the signing CA certificate needed to verify that client certificate. Never install
   the client private key on the origin.
2. Configure Nginx certificate validation in observation/testing mode with
   `ssl_verify_client optional` where appropriate. Enable or associate AOP in Cloudflare,
   then verify that Cloudflare-proxied requests present the expected client certificate.
3. Only after that verification, enforce `ssl_verify_client on`. Confirm normal
   `https://the-taragallery.com` traffic succeeds and direct-origin HTTPS without the
   client certificate fails.
4. Only after enforcement and both checks succeed may
   `ANALYTICS_TRUST_CLOUDFLARE_HEADERS=true` be considered.

Record certificate expiry and arrange reminders at 60, 30, 14 and 7 days before it.
A failed certificate rollout can make the storefront unavailable. Do not modify other
virtual hosts or global real-IP rules.

Monitor `https://the-taragallery.com/health` externally and
`http://127.0.0.1:8001/health` on the origin. External failure with internal success
points to Cloudflare/AOP/origin TLS; both failing points to backend/origin. A basic
scheduled curl with alerts is sufficient; no paid monitor is required.

## Frontend static deployment

The current production process builds `frontend/dist` and copies that build to
`/var/www/tara-store`; it does not yet have an established atomic stage/swap procedure.
The release package normalizes only `frontend/dist` to directories 0755 and files 0644
and rejects symlinks in that tree.

Before relying on staged/atomic replacement, operators must separately design, review,
test and introduce that procedure, including symlink rejection, static-file permissions,
rollback and post-swap verification. This document does not prescribe production
commands for that future procedure.
