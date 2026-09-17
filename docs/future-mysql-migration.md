# MySQL production database

**Status: exercised in CI, never deployed.** The models, types and dependencies were
chosen so that moving to MySQL 8 is a configuration change rather than a rewrite, and
since 0.3.0-rc.1 `.github/workflows/mysql-compatibility.yml` proves that against a real —
but ephemeral — MySQL 8 service on every relevant push: Alembic upgrades an empty
database to head, the migrated schema matches the models, every table is InnoDB/utf8mb4,
the client lifecycle runs and is idempotent, the demo seed runs twice without changing a
row count, and `Decimal` money, JSON config, foreign keys, unique constraints and guest
checkout all behave.

MySQL is the fixed production data store; SQLite remains intentional for local tests
and development. CI compatibility is not proof of actual server privileges, backups or
configuration. This repository audit contacts no production database. The filename is
retained because CLI diagnostics and historical records link to it.

> The CI gate installs `pip install -c constraints.txt -e ".[dev,mysql,r2]"`. The `mysql` extra pulls
> `PyMySQL[rsa]`, which MySQL 8 needs for its default `caching_sha2_password`
> authentication. A real MySQL deployment needs the same extra.

One database and one database user per client instance. No shared database, ever.

## What is already portable

| Decision | Why it helps |
| --- | --- |
| SQLAlchemy 2.x ORM throughout | ORM access keeps normal queries portable; migrations include engine-specific SQL |
| `PyMySQL` already a declared dependency | No dependency change is needed |
| Enum-like columns are `String(32)` validated by Pydantic | No native `ENUM` columns, so adding a status value stays a code change rather than a schema migration |
| Money is `Numeric(12,2)` with Python `Decimal` | Maps cleanly to MySQL `DECIMAL(12,2)`; no float rounding |
| Timestamps are naive UTC `DateTime` | Maps to `DATETIME`; no timezone semantics to reconcile |
| `JSON` for structured fields | MySQL 8 supports the configuration and metadata fields — MySQL 8 has native JSON |
| Alembic owns the schema | The same revision builds MySQL; `create_all` is only used for throwaway test databases |
| Relative-path anchoring is SQLite-only | `sqlalchemy_url()` passes any non-SQLite URL through untouched |

## Switching

The production database URL uses:

```
DATABASE_URL=mysql+pymysql://commerce_user:<password>@127.0.0.1:3306/commerce_database
```

The production template is `deployment/env/backend.env.example`. Then:

```bash
alembic upgrade head
```

## What to verify on a real server — CI does not do any of this

**1 — Charset and collation.** Create the database explicitly; do not rely on the server
default. The content is Arabic and needs full Unicode:

```sql
CREATE DATABASE commerce_CLIENT_SLUG
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

`utf8` in MySQL is not UTF-8. It must be `utf8mb4`, or four-byte characters — including
emoji in product descriptions — are silently corrupted.

**2 — Index key length.** MySQL limits index key length in bytes, and `utf8mb4` uses up to
four bytes per character. Unique indexes on long slug columns (`products.slug` is
`String(260)`) may exceed the limit and need a prefix index or a shorter column. This is
the single most likely place `alembic upgrade head` fails on a fresh MySQL database.

**3 — Arabic slugs.** Products named in Arabic get Arabic slugs. Confirm they round-trip
through MySQL, that the unique index behaves under `utf8mb4_unicode_ci`, and note that
this collation is case- and accent-insensitive, so two slugs differing only in case would
now collide where SQLite allowed both.

**4 — Check constraints.** MySQL 8.0.16+ enforces `CHECK` constraints; earlier versions
parse and ignore them. Confirm the guarantees in
[database-model.md](database-model.md) — non-negative totals, positive quantities, a
package not containing itself — are actually enforced, and pin the server version.

**5 — Strict mode.** Run with `STRICT_TRANS_TABLES`. Without it MySQL truncates
over-length values instead of raising, which would silently corrupt data that SQLite
accepted.

**6 - Search.** The existing `LIKE '%term%'` behavior remains unchanged. Verify Arabic
search against representative content; full-text indexing is outside this cleanup.

**7 — Transactions.** Use InnoDB. The order-creation path depends on real transactional
rollback to keep stock decrements and order rows consistent.

**8 — Connection pooling.** The SQLite engine sets `check_same_thread=False`, which is
SQLite-specific. For MySQL, configure `pool_size`, `max_overflow` and especially
`pool_pre_ping=True`, or connections idle past `wait_timeout` surface as
"MySQL server has gone away".

**9 — Run the suite against MySQL.** The pytest suite builds SQLite databases. The dedicated `tests_mysql` suite runs against isolated scratch MySQL databases in CI;
do not point destructive integration tests at production.

## Migrating existing data

For a store that already has live SQLite data, the schema is only half the job:

1. Back up the source database and its actual media provider as a matched set.
2. Build the MySQL schema with `alembic upgrade head` — never by dumping SQLite DDL.
3. Move rows with a script that goes through SQLAlchemy models, so `Decimal`, `DateTime`
   and `JSON` values are converted by the same code that wrote them. A raw
   `.dump` / `mysql <` pipeline will produce subtly wrong types.
4. Reset auto-increment counters, then verify row counts per table, a sample of order
   totals, and that media URLs still resolve.
5. Keep the SQLite file until the MySQL instance has been verified in use.

## Out of scope

Provisioning the server, replication, managed hosting and tuning are deployment concerns
and are not covered by this repository.
