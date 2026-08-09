# Local MySQL development runtime

**Status of live verification: PASSED on 2026-08-02.** The application has now been run
against a real MySQL 8 server: **MySQL 8.0.46**, local, `127.0.0.1:3306`, in an isolated
database `vista_store_dev` owned by an application user that can reach nothing else.

This supersedes the previous revision, which recorded the whole acceptance sequence as
**BLOCKED** because Docker was unavailable. Docker is still not installed, and nothing was
installed to work around it — the machine already had MySQL Server 8.0, so that is what
was used. `compose.mysql.dev.yml` remains in the repository as the CI-matching container
option; it is no longer the only path.

SQLite remains the default development runtime and is unchanged: the full backend suite
still runs on SQLite with no MySQL server present.

---

## The isolated local database

| | |
| --- | --- |
| Server | MySQL 8.0.46, `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe` |
| Host / port | `127.0.0.1:3306` — loopback only |
| Database | `vista_store_dev`, `utf8mb4` / `utf8mb4_unicode_ci` |
| Application user | `vista_store_dev_user`@`127.0.0.1` |
| Grants | `USAGE ON *.*` plus `ALL PRIVILEGES ON vista_store_dev.*` — **nothing else on the server is reachable** |
| Engine | every table InnoDB; 30 tables (29 application + `alembic_version`), 23 foreign keys |

The application is never run as `root`. `root` is only ever needed to create the database
and the user in the first place; once they exist it is not used again, and the acceptance
run below used the application user exclusively.

**This is not, and must never become, the cPanel production database.** It is disposable.

### Configuration

Credentials live in `.env.mysql.local` at the repository root. It is **untracked and
ignored** (`.gitignore` lists `.env.mysql.local` and `.env.mysql.app.local` explicitly).
Nothing in it is ever printed, logged or committed.

```
MYSQL_ADMIN_HOST=127.0.0.1
MYSQL_ADMIN_PORT=3306
MYSQL_ADMIN_USER=root
MYSQL_ADMIN_PASSWORD=<only needed to create the database and user>

MYSQL_DATABASE=vista_store_dev
MYSQL_APP_USER=vista_store_dev_user

DATABASE_URL=mysql+pymysql://vista_store_dev_user:<password>@127.0.0.1:3306/vista_store_dev?charset=utf8mb4
```

`?charset=utf8mb4` is not optional — without it Arabic text is stored as `latin1`
mojibake, and the damage is silent.

`backend/.env` is **not** edited: the MySQL URL is supplied as a process environment
variable for the duration of a run, so the SQLite development database and the MySQL
acceptance database can never be confused for one another. The SQLite-backed
`uvicorn` on port 8000 was stopped before the acceptance run for the same reason.

### First-time creation (needs an admin account)

```
mysql -h 127.0.0.1 -P 3306 -u root -p -e "
  CREATE DATABASE IF NOT EXISTS vista_store_dev
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER IF NOT EXISTS 'vista_store_dev_user'@'127.0.0.1' IDENTIFIED BY '<password>';
  GRANT ALL PRIVILEGES ON vista_store_dev.* TO 'vista_store_dev_user'@'127.0.0.1';
  FLUSH PRIVILEGES;"
```

Install the MySQL extra once:

```
cd backend
.venv\Scripts\python.exe -m pip install -e ".[dev,mysql]"
```

The `rsa` extra it pulls in is required because MySQL 8 defaults to
`caching_sha2_password`, which PyMySQL cannot complete without it.

---

## The acceptance sequence — result, 2026-08-02

Run from `backend/` against an empty `vista_store_dev`, with `DATABASE_URL` in the process
environment only.

| # | Step | Result |
| --- | --- | --- |
| 1 | `python -m alembic upgrade head` | ✅ `0001 → 0002 → 0003 → 0004`, clean |
| 2 | `python -m alembic current` / `heads` | ✅ **`0004_import_batches (head)`** — current equals head |
| 3 | Vista client bootstrap (`scripts.instance_cli apply --profile ../instance/vista-store.yaml`) | ✅ 12 creates, no conflict |
| 4 | Preview seed (`scripts.preview_cli seed`) | ✅ `create=54` |
| 5 | Repeat seed | ✅ `skip=53, update=1` — the single update is the batch's own seed counter |
| 6 | Temporary admin (`python -m app.initial_data`) | ✅ one `super_admin` created; the password was generated per run and never printed or stored |
| 7 | `pytest tests_mysql` | ✅ **18 passed, 4 skipped** — see "What is still blocked" |
| 8 | Arabic Unicode | ✅ `character_set_{connection,database,results} = utf8mb4`; 10/10 Arabic category names round-trip; `لآلئ إنشاء ﷺ ٢٠٢٦` survives the connection intact; no U+FFFD anywhere |
| 9 | Decimal price precision | ✅ `products.price` is `DECIMAL(12,2)`; every price reads back as a `Decimal` with `exponent == -2`; `SUM(price)` returns `Decimal('6578.90')`, not a float |
| 10 | JSON / configuration fields | ✅ `audit_logs.meta`, `home_sections.config`, `instance_metadata.enabled_features` are real `json` columns, round-trip as `dict`/`list`, and **none is indexed** |
| 11 | Foreign keys and unique constraints | ✅ 23 FK constraints, `foreign_key_checks = 1`; a dangling `order_items.order_id` and a duplicate `products.slug` are both refused with `IntegrityError` |
| 12 | Invoice sequence uniqueness | ✅ unique index on `invoices.invoice_number`; no duplicate at any point in the run |
| 13 | Cash-on-delivery order through the HTTP API | ✅ `201`, `3 × 120.25 + 25.50 = 386.25`, stock `10 → 7` |
| 14 | Confirm the order | ✅ `POST /api/v1/admin/orders/{id}/status` → 200 |
| 15 | Exactly one invoice | ✅ `INV-000001`, `issued`, `386.25` |
| 16 | Repeat the transitions (`confirmed → processing → shipped → delivered → processing → confirmed`) | ✅ all 200, **still exactly one invoice, same number** |
| 17 | Cancel the order | ✅ invoice `cancelled` with `cancelled_at` recorded, number preserved and never reused, inventory restored `7 → 10` |
| 18 | Delete one owned preview media object through the storage boundary | ✅ `storage.delete(key)`; the object is gone, its database row survives, an unrelated owned object is untouched |
| 19 | Re-run the preview seed | ✅ `repair=1, skip=52, update=1`; the object is restored at **the same key**, 12 media rows before and after, same row / same URL, 19 517 bytes; a further seed is a plain no-op |
| 20 | Preview purge, dry run | ✅ `delete=53`, nothing written |
| 21 | Preview purge, `--confirm` | ✅ `delete=66` (53 rows + 12 objects + the batch); status reports the batch is gone |
| 22 | Re-seed after purge | ✅ `create=54`, `seed_count` back to 1, 53 owned records, 0 owner-edited |

### Migration 0008 trigger deployment preflight

This is a **deployment prerequisite, not only a test detail.** Migration
`0008_order_activity_triggers` creates the two triggers that make `order_activities`
append-only. MySQL can refuse `CREATE TRIGGER` while binary logging is enabled:

```
(1419, 'You do not have the SUPER privilege and binary logging is enabled
        (you *might* want to use the less safe log_bin_trust_function_creators variable)')
```

Confirmed on MySQL 8.0.46 with `log_bin = 1` and `log_bin_trust_function_creators = 0`,
using an account granted `SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX`,
`REFERENCES, TRIGGER` on its own schema. **The `TRIGGER` privilege alone is not enough.**

The MySQL-only preflight runs before either trigger DDL. It requires the audit schema,
allows `log_bin = 0` or `log_bin_trust_function_creators = 1`, otherwise inspects
readable effective grants, and fails closed when trigger viability cannot be established.

Run migrations through a sufficiently privileged deployment/DBA account, or ask the host
to enable `log_bin_trust_function_creators = 1` temporarily. Do not change grants or
global variables from the application; restore any temporary trust setting promptly.

**Check this before a cPanel handover.** Shared hosting may not provide either
accommodation. In that case 0008 cannot be safely applied; because MySQL DDL is
non-transactional, the preflight deliberately stops before either trigger is created.

### What is still blocked

Five tests in `tests_mysql` skip because they need **further disposable databases** of
their own, and creating a database requires an administrator the application user is not:

| Test | Needs |
| --- | --- |
| `test_the_full_client_lifecycle_on_mysql` | `MYSQL_LIFECYCLE_URL` |
| `test_instance_metadata_is_recorded_and_manifest_has_no_secrets` | `MYSQL_LIFECYCLE_URL` |
| `test_a_conflicting_instance_slug_is_refused` | `MYSQL_LIFECYCLE_URL` |
| `test_the_demo_seed_is_idempotent_on_mysql` | `MYSQL_SEED_URL` |
| every test in `test_mysql_migration_order.py` | `MYSQL_MIGRATION_URL` |

To unblock them, an account that can `CREATE DATABASE` must create the schemas and grant
the application user access, then the variables must be set:

```
MYSQL_LIFECYCLE_URL=mysql+pymysql://vista_store_dev_user:<password>@127.0.0.1:3306/vista_store_dev_lifecycle?charset=utf8mb4
MYSQL_SEED_URL=mysql+pymysql://vista_store_dev_user:<password>@127.0.0.1:3306/vista_store_dev_seed?charset=utf8mb4
MYSQL_MIGRATION_URL=mysql+pymysql://vista_store_dev_user:<password>@127.0.0.1:3306/vista_store_dev_migration?charset=utf8mb4
```

`MYSQL_MIGRATION_URL` must point at a schema of its own and **nothing else**. Those tests
start each case from an empty database, so they drop every table and trigger they find.
`reset()` refuses to run unless the schema name ends in `_migration`, but that guard is a
backstop and not a substitute for pointing the variable somewhere disposable.

The `MYSQL_ADMIN_PASSWORD` currently recorded in `.env.mysql.local` is **rejected by the
server** (`ERROR 1045 Access denied for user 'root'@'localhost'`), so this could not be
done in this pass. Everything that does not require a second database was run and passed.

### A caution about running `tests_mysql` on a working database

`test_the_shipped_vista_dataset_seeds_and_purges_on_mysql` seeds **and then force-purges**
the shipped `vista-social-preview` batch. Against the empty CI service container that is
harmless; against a database you have seeded for demonstration it removes that batch. Run
`vista-preview seed` afterwards to restore it — the acceptance run above did exactly that.

Four tests in `tests_mysql/test_mysql_preview.py` used to resolve their subject with
"the first row of this table". On the empty CI container that is the row they created; on
a real development database it is somebody else's. They now resolve every row through the
`ImportBatchRecord` that owns it, which is what the importer's own safety rules use.

---

## What to check explicitly

| Property | How | 2026-08-02 |
| --- | --- | --- |
| Decimal money precision | `SELECT price FROM products` — two decimal places, no float drift | ✅ step 9 |
| JSON / configuration fields | `home_sections.config`, `instance_metadata.enabled_features`, `audit_logs.meta` — objects, none indexed | ✅ step 10 |
| Unicode Arabic content | `SHOW VARIABLES LIKE 'character_set_%'` is `utf8mb4`; `لآلئ` and `ﷺ` survive | ✅ step 8 |
| Unique constraints | duplicate `products.slug`, `import_batches.batch_key`, `(batch_id, entity_type, entity_id)` all raise `IntegrityError` | ✅ steps 7, 11 |
| Foreign keys | InnoDB enforces them, unlike SQLite's default | ✅ step 11 |
| Invoice sequencing | one invoice per order, number never reused, unique index | ✅ steps 12, 15–17 |
| Alembic revision | `python -m alembic current` reports `0004_import_batches (head)` | ✅ step 2 |
| Preview batch ownership | `vista-preview status` — 53 records, 0 owner-edited | ✅ step 22 |
| Preview media repair | delete an owned object, re-seed, expect `repair=1` and no new row | ✅ steps 18–19 |

---

## Scope guarantees

* Only `vista_store_dev` on `127.0.0.1:3306` was contacted. No remote server, no
  production database, no other schema on this machine — the application user cannot see
  one.
* The application was never run as `root`; `root` was not used at all in this pass.
* Nothing was installed to make this work beyond the project's own `mysql` extra.
  No Docker, no second database server.
* Credentials stay in `.env.mysql.local`, which is ignored by Git and was confirmed
  untracked.
* `backend/.env` still points at SQLite, so a developer who does nothing gets SQLite.
