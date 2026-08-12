# Client instance lifecycle

One client, one independent instance: its own checkout, process, database, media
directory, domain and credentials. Nothing is shared. This page covers create, operate,
upgrade, and backup/restore.

Two rules underpin all of it:

- **A client database is never copied from the development SQLite database.** It is always
  created empty and built by Alembic.
- **Secrets live only in the untracked environment file.** The instance profile is
  non-secret by design and validation rejects credential-shaped keys.

## The two initialization workflows

They are deliberately separate. Confusing them is the main way to damage a client store.

| | Demo seed | Client bootstrap |
| --- | --- | --- |
| Command | `python -m scripts.seed` | `python -m scripts.instance_cli apply` |
| Purpose | Development and demonstration | Real client instances |
| Creates | Sample categories, products, variants, packages, coupons, articles, a demo order | Store settings, home page sections, static pages, delivery areas |
| Commercial data | Yes, all fabricated | **None** |
| Admin account | Only if credentials are passed | **Never** |
| On re-run | Rewrites its own seeded content, including resetting seeded stock | Creates only what is missing; **never overwrites owner edits** |

Admin creation is a third, always-explicit step: `python -m app.initial_data`.

**Never run the demo seed against a client store.**

## Create

### 1 — Choose a released template version

Check `VERSION` and `CHANGELOG.md`. Deploy from a released version, not an arbitrary
commit.

### 2 — Copy and customize a profile

```powershell
cd D:\Project\vista-store-e-commerce
copy instance\client-profile.example.yaml instance\acme-profile.yaml
```

Edit it: `client_slug`, store name and tagline, locale, timezone, currency, domain,
contact defaults, theme colours, features, home sections, static pages (with the client's
approved copy in `content:` where it exists) and delivery areas. Set `template_version` to
the release you are deploying.

The `client_slug` is permanent. It is written to the database, and a later `apply` with a
different slug is refused rather than silently rebranding a live store.

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.instance_cli validate --profile ..\instance\acme-profile.yaml
```

`validate` touches no database, so it works before anything else is configured.

### 3 — Create the untracked environment file

```powershell
copy backend\.env.example backend\.env
```

Set, at minimum:

- `SECRET_KEY` — unique per instance: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `APP_ENV=production`
- `DATABASE_URL` — **a new, empty database for this client**
- `CORS_ORIGINS` — the client's real domain
- `LOCAL_MEDIA_ROOT` — a directory the service user can write to

Never put any of this in the profile. `chmod 600` the file and confirm
`git check-ignore -v backend/.env`.

### 4 — Build the schema

```powershell
.venv\Scripts\alembic.exe upgrade head
```

This creates every table from migrations. Do not import a dump of the development
database, and do not copy `commerce_dev.db`.

### 5 — Plan, then apply

```powershell
.venv\Scripts\python.exe -m scripts.instance_cli plan  --profile ..\instance\acme-profile.yaml
.venv\Scripts\python.exe -m scripts.instance_cli apply --profile ..\instance\acme-profile.yaml
```

`plan` prints exactly what `apply` will do — `create`, `skip` or `conflict` — and writes
nothing. Read it before applying.

`apply` initializes store settings, home page sections and static pages, and records
`instance_metadata`. It is idempotent, so re-running it is safe.

### 6 — Create the first administrator, separately

```powershell
.venv\Scripts\python.exe -m app.initial_data --email owner@example.com --password '<generated>'
```

Generate the password, deliver it out of band, and have it changed at first sign-in. It
never comes from the profile.

### 7 — Record the instance

```powershell
.venv\Scripts\python.exe -m scripts.instance_cli manifest --output ..\instance\acme-manifest.json
```

The manifest is non-secret: instance slug, template version, profile schema version,
current Alembic revision, enabled features and initialization timestamps. Keep it with the
client's records — it answers "what is running, and which template did it come from".

Then follow [deployment-templates.md](deployment-templates.md) for the service and web
server, and [new-client-checklist.md](new-client-checklist.md) for the full handover list.

## Operate

Day-to-day, the owner works entirely through Admin: products, categories, orders,
coupons, delivery areas, hero slides, banners, home sections, articles, pages, media and
settings. See [admin-capabilities.md](admin-capabilities.md).

Keep runtime state out of Git — the database, uploaded media and `.env` are all ignored,
and must stay that way.

The profile is a *starting point*, not a live configuration file. Once an instance is
running, Admin is authoritative. Re-applying a profile will not undo owner edits, and
editing a profile after go-live changes nothing by itself.

## Upgrade

1. **Back up the database and media together** — see below. Do this first.
2. Note the current state: `commerce-instance manifest`.
3. Deploy the newer template release (`git fetch`, check out the release, reinstall
   backend dependencies, `npm ci && npm run build`).
4. **Run migrations**: `alembic upgrade head`.
5. **Record the new template version**: re-run `instance_cli apply` with the instance's
   profile. It refreshes `template_version` and `last_bootstrap_at` in `instance_metadata`,
   creates anything the new release added, and leaves owner content alone.
6. Regenerate the manifest.
7. **Smoke check**: `/health` returns 200; the storefront home page loads; a product page
   loads; a deep link survives a reload; `/admin/login` signs in; `/api/v1/admin/dashboard`
   returns 401 without a token; an uploaded image still resolves.

Roll back by restoring the backup and redeploying the previous release. Alembic
`downgrade` is a last resort — restoring is safer.

## Backup and restore

The database and the media directory are backed up **together** and restored **together**;
they reference each other. Full procedure, including verification, in
[backup-and-restore.md](backup-and-restore.md).

**The instance profile is not a backup.** It describes initial identity and defaults, not
the store's data. Restoring a profile recreates neither products, nor orders, nor edited
content. Back up:

- the database
- `LOCAL_MEDIA_ROOT`
- `backend/.env`, stored separately and encrypted

Keep the profile and manifest in version control or with the client's records, so an
instance can be rebuilt to the same starting shape — but recognise that rebuilding from a
profile gives an empty store, not the client's data.

## Future: instance factory (not implemented)

A later, server-side phase may automate provisioning with the same
**`validate` → `plan` → `apply`** shape as the instance CLI, so a dry run is always
available before anything is changed.

Such a tool could create:

- the project directory
- an empty database and a restricted database user
- the environment file, with a generated `SECRET_KEY`
- the systemd service
- the Nginx site
- the media directory and its permissions
- backup configuration

**None of this exists today, and nothing in this repository modifies server services,
databases or Nginx.** The templates in `deployment/` are inactive examples that a human
copies, edits and installs. Building the factory would need its own design: privilege
boundaries, credential generation and handling, rollback of a partial apply, and port and
slug allocation across instances.

Until then, provisioning is the manual checklist in
[new-client-checklist.md](new-client-checklist.md).
