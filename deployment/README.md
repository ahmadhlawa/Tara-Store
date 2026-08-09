# Deployment templates — examples only, nothing here is active

Every file in this directory is an **inactive example**. Nothing in this repository
deploys itself, and no file here is read by the application at runtime. Copy a template
out, replace the placeholders, review it, and only then install it on a server.

These templates were written and reviewed locally. **They have never been installed or
executed on any server**, so treat them as a starting point that a human must verify —
not as a proven configuration.

## Placeholders

Replace all four in every file you copy. They are the only placeholders used.

| Placeholder | Meaning | Example value |
| --- | --- | --- |
| `CLIENT_SLUG` | Short lowercase identifier for the client instance | `northwind` |
| `CLIENT_DOMAIN` | Public domain that serves the storefront | `shop.example.com` |
| `BACKEND_PORT` | Loopback port for this instance's FastAPI service | `8001` |
| `PROJECT_PATH` | Absolute path of the instance checkout on the server | `/srv/commerce/northwind` |

Check that nothing is left over before installing anything:

```bash
grep -rn "CLIENT_SLUG\|CLIENT_DOMAIN\|BACKEND_PORT\|PROJECT_PATH" /etc/nginx/sites-available/commerce-northwind.conf
```

## One instance per client

This template is deployed as a **separate, independent instance per client**. There is no
multi-tenancy, no `tenant_id`, and no shared database. Two clients never share a process,
a database, a media directory, or a domain.

Each instance gets its own:

- checkout directory (`PROJECT_PATH`)
- systemd unit (`commerce-CLIENT_SLUG.service`)
- loopback port (`BACKEND_PORT`) — allocate a distinct one per instance
- Nginx server block and domain (`CLIENT_DOMAIN`)
- database and database user
- `.env` file and `SECRET_KEY`
- media directory

### Naming convention

| Item | Pattern | Example |
| --- | --- | --- |
| Checkout directory | `PROJECT_PATH` | `/srv/commerce/northwind` |
| systemd unit | `commerce-CLIENT_SLUG.service` | `commerce-northwind.service` |
| Nginx site | `commerce-CLIENT_SLUG.conf` | `commerce-northwind.conf` |
| System user | `commerce-CLIENT_SLUG` | `commerce-northwind` |
| Database | `commerce_CLIENT_SLUG` | `commerce_northwind` |
| Database user | `commerce_CLIENT_SLUG` | `commerce_northwind` |
| Backend port | one free loopback port | `8001`, `8002`, … |

Keep a record of which port belongs to which instance; the templates cannot enforce it.

## Files

| File | Purpose |
| --- | --- |
| `systemd/commerce-CLIENT_SLUG.service.example` | Runs the FastAPI backend under Uvicorn |
| `nginx/commerce-CLIENT_SLUG.conf.example` | Serves the built SPA, reverse-proxies `/api`, serves `/media` |
| `env/backend.env.example` | Pointer to the authoritative `backend/.env.example` |

## Deployment checklist

Work through this in order. Stop at anything that does not behave as described.

**1 — Prepare the instance**

- [ ] Create the system user `commerce-CLIENT_SLUG` with no login shell.
- [ ] Create `PROJECT_PATH` and check the repository out into it.
- [ ] Choose a free `BACKEND_PORT` and record which instance owns it.

**2 — Configure**

- [ ] Copy `backend/.env.example` to `PROJECT_PATH/backend/.env`.
- [ ] Generate a unique `SECRET_KEY`:
      `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] Set `APP_ENV=production`.
- [ ] Set `DATABASE_URL` for this instance's own database.
- [ ] Set `CORS_ORIGINS=https://CLIENT_DOMAIN` (comma-separated if more than one).
- [ ] Set `LOCAL_MEDIA_ROOT` to a directory the service user can write to.
- [ ] Leave `INITIAL_ADMIN_*` empty; create the admin explicitly in step 4.
- [ ] `chmod 600` the `.env` and make the service user its owner.
- [ ] Confirm `.env` is not tracked by Git.

**3 — Build**

- [ ] Backend: create a virtualenv and `pip install .` from `PROJECT_PATH/backend`.
- [ ] Frontend: `npm ci && npm run build` in `PROJECT_PATH/frontend`, producing `dist/`.
- [ ] Apply the schema: `alembic upgrade head`.
- [ ] Optionally seed demo content: `python -m scripts.seed`.
      Do **not** seed a real client's live store — the seed rewrites seeded product stock
      on every run.

**4 — Create the administrator**

- [ ] `python -m app.initial_data --email <admin address> --password '<generated>'`
- [ ] Hand the password over out of band and have it changed on first sign-in.
- [ ] Never commit it and never put it in the unit file.

**5 — Install the service**

- [ ] Copy the systemd template, substitute the placeholders, install it, and enable it.
- [ ] Confirm the service is listening on `127.0.0.1:BACKEND_PORT` only.
- [ ] `curl http://127.0.0.1:BACKEND_PORT/health` returns `{"status":"ok",...}`.

**6 — Install the web server configuration**

- [ ] Copy the Nginx template, substitute the placeholders, and enable the site.
- [ ] Issue a TLS certificate for `CLIENT_DOMAIN` and enable HTTPS redirection.
- [ ] `nginx -t`, then reload.

**7 — Verify the deployed instance**

- [ ] `https://CLIENT_DOMAIN/` serves the storefront.
- [ ] A deep link such as `https://CLIENT_DOMAIN/product/<slug>` loads directly
      (SPA fallback works) rather than returning 404.
- [ ] `https://CLIENT_DOMAIN/api/v1/store/settings` returns JSON.
- [ ] An uploaded image is reachable under `https://CLIENT_DOMAIN/media/...`.
- [ ] `https://CLIENT_DOMAIN/admin/login` signs in, and `/api/v1/admin/dashboard`
      returns 401 without a token.
- [ ] Place a test order, then delete it before handover.

**8 — Operational**

- [ ] Back up the database and the media directory together; see
      `docs/backup-and-restore.md`.
- [ ] Add rate limiting in front of `/api/v1/auth/login` — the application does not
      implement it.
- [ ] Pin the Python version; the code targets 3.12+.

## Out of scope for these templates

No content here provisions DNS, issues certificates, configures a firewall, sets up a
database server, or configures object storage. They also do not configure Cloudflare R2:
the storage adapter exists in the codebase but is inert and raises a configuration error
if selected without credentials. Local disk storage is the only supported provider today.
