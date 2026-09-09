# Local development setup

Everything here runs on one machine against local SQLite. No database server, no object
storage account and no network services are required.

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.12 or newer | The reference environment currently runs 3.13 |
| Node.js | 22 | Matches CI and the supported application runtime |
| Git | any recent | |

## First run

### 1 — Backend

```powershell
cd D:\Project\Tara-Store\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev]"
```

`-e ".[dev]"` installs the application in editable mode together with pytest, coverage and
the other development dependencies declared in `pyproject.toml`.

### 2 — Configuration

```powershell
copy .env.example .env
```

Then edit `backend\.env`:

- **`SECRET_KEY`** — generate a real one. Tokens signed with the placeholder are
  worthless, and changing it later signs every administrator out.

  ```powershell
  .venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

- Leave everything else at its default for local work. `DATABASE_URL` already points at
  `./data/tara_store_dev.db`, and relative SQLite paths are anchored to `backend/`, not to
  your current directory, so the file lands in the same place wherever you run from.

`.env` is git-ignored. Confirm it if you are unsure:

```powershell
git check-ignore -v backend\.env
```

`CORS_ORIGINS` accepts a comma-separated list (`http://localhost:5173,http://127.0.0.1:5173`).
A JSON array works too.

### 3 — Schema and data

```powershell
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m scripts.instance_cli apply --profile ..\instance\tara-store.yaml
```

`alembic upgrade head` applies the full migration chain through current head
`0014_remove_content`.

> `scripts.seed` is optional, isolated demo/test tooling. It creates sample products,
> orders, coupons and media; it is not part of Tara's normal first-run workflow.
>
> **NEVER run it against `tara_store_dev.db` once real client data entry begins.** See
> [client-lifecycle.md](client-lifecycle.md).

`scripts.seed` fills the store with demo content and is **idempotent** — every record is
matched on its natural key, so running it twice changes nothing. It writes real gradient
PNGs into the media directory so seeded content has working images without committing
binaries. A typical run reports:

```
artwork: 13 placeholder images      categories: 15      products: 31
variants: 9                         package items: 8    hero slides: 3
banners: 3                          home sections: 8    coupons: 2
delivery areas: 5                   articles: 4         static pages: 6
demo order: ORD-YYMMDD-NNNN         admin: skipped (no credentials supplied)
```

The seed deliberately does **not** create an administrator unless you supply credentials,
so an unconfigured instance has no usable admin account at all.

### 4 — An administrator

```powershell
.venv\Scripts\python.exe -m app.initial_data --email you@example.com --password '<choose one>'
```

Use a real address format; `.local` and similar reserved suffixes are rejected by the
email validator. The first account created is a `super_admin`.

### 5 — Run both halves

```powershell
# terminal 1
cd D:\Project\Tara-Store\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# terminal 2
cd D:\Project\Tara-Store\frontend
npm ci
npm run dev
```

| URL | What |
| --- | --- |
| <http://localhost:5173> | Storefront |
| <http://localhost:5173/admin/login> | Admin workspace |
| <http://127.0.0.1:8000/docs> | Interactive API documentation |
| <http://127.0.0.1:8000/health> | Health check |

The Vite dev server proxies `/api`, `/media` and `/health` to `127.0.0.1:8000`, so the
browser talks to a single origin and no CORS configuration is needed in development. If
you run the backend on another port, set `VITE_DEV_API_TARGET` in
`frontend/.env.local`. The canonical local runtime is Vite 5173 proxying backend 8000.

## Daily workflow

```powershell
cd backend  ; .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
cd frontend ; npm run dev
```

Both reload on save. After pulling changes that touch `backend/app/models/`, run
`alembic upgrade head` again.

## Tests

```powershell
cd D:\Project\Tara-Store\backend
.venv\Scripts\python.exe -m pytest                 # full backend suite
.venv\Scripts\python.exe -m pytest --cov=app       # with coverage

cd D:\Project\Tara-Store\frontend
npm test -- --run                                  # unit tests
npm run test:watch                                 # watch mode
```

Backend tests build their own throwaway SQLite database and never touch
`tara_store_dev.db`. Frontend tests run under jsdom with `fetch` stubbed; they never reach a
real server.

## Instance tooling

Four commands manage an instance's identity. All are local and touch no server.

```powershell
cd D:\Project\Tara-Store\backend
.venv\Scripts\python.exe -m scripts.instance_cli validate --profile ..\instance\tara-store.yaml
.venv\Scripts\python.exe -m scripts.instance_cli plan     --profile ..\instance\tara-store.yaml
.venv\Scripts\python.exe -m scripts.instance_cli apply    --profile ..\instance\tara-store.yaml
.venv\Scripts\python.exe -m scripts.instance_cli manifest
```

`validate` needs no database; `plan` writes nothing; `apply` is idempotent and never
overwrites content edited through Admin.

The offline MySQL portability check connects to nothing:

```powershell
.venv\Scripts\python.exe -m scripts.mysql_compat --verbose
```

## Production build check

```powershell
cd D:\Project\Tara-Store\frontend
npm run build       # emits dist/
npm run preview     # serves the build locally
```

`vite preview` does not reproduce a production web server. Deep links rely on an SPA
fallback that Nginx provides in a real deployment — see
[deployment-templates.md](deployment-templates.md).

## Troubleshooting

**`SettingsError: error parsing value for field "CORS_ORIGINS"`**
An old checkout. `CORS_ORIGINS` is annotated so the comma-separated form in `.env.example`
parses; update to a revision that includes that fix.

**`alembic: command not found`**
Call it through the virtualenv: `.venv\Scripts\alembic.exe`, not a global `alembic`.

**The database seems empty after switching branches**
`*.db` files are git-ignored, so branch switches do not carry them. Re-run
`alembic upgrade head` and `scripts.seed`.

**`[Errno 10048] only one usage of each socket address`**
Port 8000 is already taken, often by an earlier `uvicorn` that is still running. Use
another port, and remember to point the frontend at it.

**Login always fails**
Confirm an admin exists (`app.initial_data`), that the account is active, and that
`SECRET_KEY` has not changed since the token was issued.

**Images 404 in development**
They are served through the `/media` proxy from `LOCAL_MEDIA_ROOT`. Check the backend is
running and that `backend/data/tara-uploads/` contains the files.

**Arabic slugs in URLs**
Products named in Arabic get Arabic slugs. Browsers percent-encode them automatically;
command-line clients such as `curl` may need the URL encoded by hand.
