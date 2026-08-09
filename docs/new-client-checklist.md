# New client checklist

Cloning the template for a new client. One independent instance per client: separate
checkout, process, database, media directory, domain and credentials. Nothing is shared —
no `tenant_id`, no shared database, no shared bucket.

## 0 — Decide the identifiers first

Fix these before touching anything; they appear throughout the instance.

| Item | Value |
| --- | --- |
| `CLIENT_SLUG` | short, lowercase, no spaces |
| `CLIENT_DOMAIN` | the public domain |
| `BACKEND_PORT` | a free loopback port, unique across instances on the host |
| `PROJECT_PATH` | absolute path of the checkout |

Record the port allocation somewhere durable. Nothing in the repository can enforce
uniqueness across instances.

## 1 — Create the instance

- [ ] Clone the template repository to `PROJECT_PATH`.
- [ ] Create a client branch, or an independent repository if the client's store will
      diverge from the template. Decide this now — retrofitting is painful.
- [ ] Confirm the working tree is clean and no `.env`, database file or media came along.

## 2 — Configure

- [ ] `cp backend/.env.example backend/.env`
- [ ] Generate a unique `SECRET_KEY`:
      `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] `APP_ENV=production`
- [ ] `APP_NAME` — the client's store name
- [ ] `DATABASE_URL` — this client's own database and user
- [ ] `CORS_ORIGINS=https://CLIENT_DOMAIN`
- [ ] `LOCAL_MEDIA_ROOT` — writable by the service user, matching the Nginx `alias`
- [ ] Leave `R2_*` empty unless object storage is actually being set up
- [ ] Leave `INITIAL_ADMIN_*` empty; create the administrator explicitly in step 4
- [ ] `chmod 600 backend/.env`, owned by the service user
- [ ] `git check-ignore -v backend/.env` confirms it is ignored

## 3 — Build and apply the schema

- [ ] Backend virtualenv, then `pip install .` (production; `-e ".[dev]"` only for
      development machines)
- [ ] `alembic upgrade head`
- [ ] `cd frontend && npm ci && npm run build` → `dist/`
- [ ] Decide about the seed:
      - **Demo or pilot instance** — `python -m scripts.seed` gives a fully populated store
      - **Real client store** — **do not seed.** The seed inserts demo Arabic products and
        resets seeded stock on every run. Start empty and let the client's catalogue be the
        only content

## 4 — Create the administrator

```bash
python -m app.initial_data --email <client address> --password '<generated>'
```

- [ ] Generate the password; do not invent a memorable one.
- [ ] Deliver it out of band and require a change at first sign-in.
- [ ] Never put it in the unit file, the repository or a ticket.
- [ ] Create a second super admin only if the client genuinely needs one — the last active
      super admin cannot be deleted, which is a safety net, not a licence to make several.

## 5 — Service and web server

- [ ] Copy `deployment/systemd/commerce-CLIENT_SLUG.service.example`, substitute the
      placeholders, install, enable, start.
- [ ] `curl http://127.0.0.1:BACKEND_PORT/health` returns `{"status":"ok",...}`.
- [ ] Copy `deployment/nginx/commerce-CLIENT_SLUG.conf.example`, substitute, enable.
- [ ] Issue a TLS certificate for `CLIENT_DOMAIN`; confirm HTTP redirects to HTTPS.
- [ ] `nginx -t`, reload.
- [ ] Confirm no placeholder survives in either installed file.

## 6 — Brand the store through the admin area, not the code

The template must stay client-neutral. Everything below is data:

- [ ] `/admin/settings` — name, tagline, logo, favicon, contact details, WhatsApp, social
      links, brand colours, currency, default SEO
- [ ] `/admin/media` — upload the client's images
- [ ] `/admin/categories` and `/admin/products` — the real catalogue
- [ ] `/admin/delivery` — real areas and fees
- [ ] `/admin/hero`, `/admin/banners`, `/admin/home` — home page composition
- [ ] `/admin/pages` — About, Privacy Policy, Return Policy, Terms. These are linked
      directly from the storefront footer; leaving them empty leaves visible dead ends
- [ ] `/admin/coupons` — if the client wants any

**Do not hard-code a client name, logo, colour or phone number anywhere in the
repository.** If something cannot currently be set through the admin area, that is a gap to
fix in the template, not a reason to hard-code it in a client copy.

## 7 — Verify the live instance

- [ ] `https://CLIENT_DOMAIN/` serves the storefront
- [ ] A deep link such as `https://CLIENT_DOMAIN/product/<slug>` loads on reload — proves
      the SPA fallback works
- [ ] `https://CLIENT_DOMAIN/api/v1/store/settings` returns the client's identity
- [ ] An uploaded image loads under `https://CLIENT_DOMAIN/media/...`
- [ ] `/admin/login` signs in; `/api/v1/admin/dashboard` returns 401 without a token
- [ ] Place a real test order end to end, confirm it appears in `/admin/orders`, change its
      status, then **delete the test data before handover**
- [ ] Confirm stock decremented on the order and was restored on cancellation
- [ ] Check the storefront on a phone-width viewport — the design is RTL and responsive,
      but each client's content length differs

## 8 — Operational handover

- [ ] Backups configured for both the database and the media directory, together — see
      [backup-and-restore.md](backup-and-restore.md)
- [ ] A restore has actually been rehearsed once
- [ ] Rate limiting added in front of `/api/v1/auth/login`; the application has none
- [ ] Python version pinned (3.12+)
- [ ] Someone knows how to reach the logs: `journalctl -u commerce-CLIENT_SLUG -f`
- [ ] The client knows the admin URL, their credentials, and that there is no
      password-reset email flow — a lost password needs another super admin or a
      command-line reset

## 9 — Record it

Keep one line per instance somewhere you will find it again: client, slug, domain, port,
path, database name, and where the credentials are stored.

## Do not

- Do not point two clients at one database, one bucket or one process.
- Do not copy a `.env`, a database file or uploaded media between clients.
- Do not reuse a `SECRET_KEY` across instances — one leak would compromise all of them.
- Do not seed demo data into a live client store.
- Do not commit client branding back into the template.
