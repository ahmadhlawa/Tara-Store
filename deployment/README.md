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
from other projects. Use `R2_OBJECT_PREFIX=tara/` and Tara-scoped bucket credentials.
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
   `0026_prelaunch_sanitation` is the current repository head; translations remain
   in `0025_translations`. Do not rewrite migrations or
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
