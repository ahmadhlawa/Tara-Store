# SQLite workflow

SQLite is the local development and test database. It needs no server, and the file is
git-ignored. MySQL 8 is the intended server target — see
[future-mysql-migration.md](future-mysql-migration.md).

Default location, from `backend/.env`:

```
DATABASE_URL=sqlite+pysqlite:///./data/commerce_dev.db
```

Relative SQLite paths are anchored to `backend/`, not to the process working directory, so
Alembic, the seed script and the application all resolve to the same file no matter where
they are launched from.

All commands below assume:

```powershell
cd D:\Project\vista-store-e-commerce\backend
```

## Migrations

```powershell
.venv\Scripts\alembic.exe upgrade head      # apply everything
.venv\Scripts\alembic.exe current           # what is applied now
.venv\Scripts\alembic.exe history           # revisions
.venv\Scripts\alembic.exe downgrade -1      # step back one
```

A clean database goes to `0001_initial (head)` and gains all 23 tables.

### Adding a migration

```powershell
.venv\Scripts\alembic.exe revision --autogenerate -m "add product badge"
```

**Read the generated file before applying it.** Autogenerate does not reliably detect
renames, check constraints, server defaults or type changes, and against SQLite it cannot
express every `ALTER` — Alembic falls back to batch operations. If a change is awkward on
SQLite, write the operations by hand rather than working around them in application code.

`tests/test_migrations.py` compares the migrated schema against `Base.metadata`, so a
model that drifts from its migration fails the suite.

## Seeding

```powershell
.venv\Scripts\python.exe -m scripts.seed
```

Idempotent: every record is matched on its natural key (slug, code, name or section key),
so a second run changes nothing. It writes real gradient PNGs into `LOCAL_MEDIA_ROOT` and
registers them as media assets, so seeded content has working images without committing
binaries.

Two things worth knowing:

- The seed **resets seeded product stock** to its seed values on every run, which undoes
  stock movements from demo orders. Fine locally; do not run it against a live store.
- It creates **no administrator** unless credentials are supplied, so an unconfigured
  instance has no usable admin account.

```powershell
.venv\Scripts\python.exe -m scripts.seed --admin-email you@example.com --password '<choose>'
# or separately:
.venv\Scripts\python.exe -m app.initial_data --email you@example.com --password '<choose>'
```

## Starting over

The database is a file; deleting it is the reset.

```powershell
.venv\Scripts\python.exe -m uvicorn --version   # make sure nothing is running first
Remove-Item .\data\commerce_dev.db -Force
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m scripts.seed
.venv\Scripts\python.exe -m app.initial_data --email you@example.com --password '<choose>'
```

To also clear uploaded media:

```powershell
Get-ChildItem .\data\uploads -Exclude .gitkeep | Remove-Item -Force
```

Keep `.gitkeep` — it is the only tracked file in that directory, and a parent-level
`uploads/` ignore rule would make tracking it impossible. That is why no such rule exists
in `.gitignore`.

## A throwaway database

To try a migration or the seed without touching your working database:

```powershell
$env:DATABASE_URL="sqlite+pysqlite:///./data/scratch.db"
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m scripts.seed
Remove-Item .\data\scratch.db -Force
Remove-Item Env:\DATABASE_URL
```

`DATABASE_URL` in the environment overrides the `.env` value.

For browser validation, point Vite and uvicorn at the same timestamped disposable file
and check `/api/v1/openapi.json` through port 5173 before mutating scenarios.
For a fixture with uploaded media, point `LOCAL_MEDIA_ROOT` at its matching timestamped
`*_uploads` directory as well.
This is local development fixture guidance; production/staging storage validation is
deferred until its infrastructure and real data are available.

## Inspecting the database

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'data\commerce_dev.db'); print([r[0] for r in c.execute(\"select name from sqlite_master where type='table' order by name\")])"
```

Or from Python:

```python
from app.db.session import SessionLocal
from app.models import Product

with SessionLocal() as db:
    print(db.query(Product).count())
```

Any SQLite browser works too — open the file read-only while the server is running.

## Backups

The file is the backup, but copying it while the server is writing can capture a torn
state. Use SQLite's own backup:

```powershell
.venv\Scripts\python.exe -c "import sqlite3; s=sqlite3.connect(r'data\commerce_dev.db'); d=sqlite3.connect(r'data\backup.db'); s.backup(d); d.close(); s.close()"
```

Back up `data/uploads/` at the same time, or the restored database will reference images
that no longer exist. See [backup-and-restore.md](backup-and-restore.md).

## Limits to keep in mind

- **One writer at a time.** Concurrent writes surface as `database is locked`. Irrelevant
  for local work, a real constraint for a busy store — one reason MySQL is the server
  target.
- **Loose typing.** SQLite will accept values MySQL rejects, so a schema that behaves
  locally can still fail on MySQL. The models were written to be portable, but portability
  is designed for and not yet tested.
- **`LIKE` search only.** `Product.search_text` plus `LIKE` is correct but unindexed for
  full-text purposes; at scale MySQL wants a proper full-text index.
