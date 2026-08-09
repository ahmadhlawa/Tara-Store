# Backup and restore

The single most important point: **the database and the media directory must be backed up
together, and restored together.** They reference each other. A database restored without
its media shows broken images; media restored without its database is a directory of
anonymous hex filenames with nothing describing them.

## What to back up

| What | Where | Why |
| --- | --- | --- |
| Database | `DATABASE_URL` — SQLite file, or the MySQL database | Orders, catalogue, settings, admins |
| Uploaded media | `LOCAL_MEDIA_ROOT` (default `backend/data/uploads/`) | The image bytes; the database stores only names and URLs |
| `backend/.env` | The instance | `SECRET_KEY` and credentials. **Store separately, encrypted** |

Not worth backing up — all reproducible from the repository: `node_modules/`,
`frontend/dist/`, `backend/.venv/`, `__pycache__/`.

`backend/.env` deserves care. Restoring a database with a *different* `SECRET_KEY` is
fine — it just signs every administrator out. Losing `.env` entirely means reconstructing
the database credentials by hand.

## Backing up SQLite

Do **not** copy the file while the service is writing to it; you can capture a torn state.
Use SQLite's own backup API, which is safe on a live database:

```bash
python -c "import sqlite3; s=sqlite3.connect('data/commerce_dev.db'); d=sqlite3.connect('data/backup.db'); s.backup(d); d.close(); s.close()"
```

Or, if `sqlite3` is installed:

```bash
sqlite3 data/commerce_dev.db ".backup 'data/backup.db'"
```

Then archive the database and the media together, so the pair can never be separated:

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
tar czf commerce-CLIENT_SLUG-$STAMP.tar.gz data/backup.db data/uploads
rm data/backup.db
```

## Backing up MySQL

```bash
mysqldump --single-transaction --routines --default-character-set=utf8mb4 \
  -u commerce_CLIENT_SLUG -p commerce_CLIENT_SLUG > db-$STAMP.sql
tar czf commerce-CLIENT_SLUG-$STAMP.tar.gz db-$STAMP.sql data/uploads
```

`--single-transaction` gives a consistent snapshot on InnoDB without locking the store.
`--default-character-set=utf8mb4` is not optional — the content is Arabic, and dumping
through a narrower charset corrupts it silently.

Never put the password on the command line; use `--defaults-extra-file` or the interactive
prompt.

## Scheduling

Whatever schedule you choose, three properties matter more than frequency:

- **Off-host.** A backup on the same disk as the store is not a backup.
- **Retained in generations.** Keep several — corruption is often noticed days later.
- **Monitored.** A backup job that has been failing silently for a month is the normal
  failure mode.

A daily archive with, say, fourteen days of retention suits a small store. Match it to how
much order history the client could bear to re-enter by hand.

## Restoring

Stop the service first, so nothing writes while you swap files underneath it.

```bash
systemctl stop commerce-CLIENT_SLUG
```

**SQLite**

```bash
tar xzf commerce-CLIENT_SLUG-STAMP.tar.gz -C /tmp/restore
cp /tmp/restore/data/backup.db PROJECT_PATH/backend/data/commerce_dev.db
rsync -a --delete /tmp/restore/data/uploads/ PROJECT_PATH/backend/data/uploads/
chown -R commerce-CLIENT_SLUG:commerce-CLIENT_SLUG PROJECT_PATH/backend/data
```

**MySQL**

```bash
mysql -u commerce_CLIENT_SLUG -p --default-character-set=utf8mb4 \
  commerce_CLIENT_SLUG < db-STAMP.sql
rsync -a --delete /tmp/restore/data/uploads/ PROJECT_PATH/backend/data/uploads/
```

Then bring it back up and reconcile the schema:

```bash
systemctl start commerce-CLIENT_SLUG
cd PROJECT_PATH/backend && .venv/bin/alembic upgrade head
```

`alembic upgrade head` matters when restoring an **older** backup into a **newer** code
deployment: the data is at an older revision and must be migrated forward. It is a no-op
if the revisions already match.

## Verifying a restore

A backup you have never restored is a hypothesis. Check all of these:

- [ ] `curl http://127.0.0.1:BACKEND_PORT/health` returns 200
- [ ] `alembic current` reports the expected revision
- [ ] Order count and the most recent order number match the source
- [ ] A product page loads **with its images** — this is what catches a media/database
      mismatch
- [ ] An administrator can sign in. If `SECRET_KEY` changed, everyone was signed out;
      that is expected, not a failed restore
- [ ] Store settings show the client's identity, not template defaults

Rehearse a restore into a scratch instance at least once before handover, not during the
first real incident.

## Things that will bite you

- **Restoring the database alone.** The commonest mistake. Products keep their image URLs,
  the files are gone, and every product falls back to a gradient placeholder.
- **Restoring media alone.** Filenames are `uuid4().hex`; without the database rows
  nothing can be reassociated.
- **`rsync` without `--delete`** leaves files from the failed state mixed into the restored
  set. Usually harmless, occasionally confusing.
- **Running `scripts.seed` on a restored production store.** It resets seeded product stock
  and inserts demo content. Never run it against a live client store.
- **Forgetting `.env`.** The application starts with defaults and a random-looking failure
  rather than a clear one.

## If media moves to R2

The two halves separate: the database is backed up as above, while object storage needs
its own strategy — bucket versioning, lifecycle rules, or a periodic sync to another
bucket. Ensure a database backup and an object-storage snapshot can be matched by time, or
you lose the ability to restore a consistent pair. See
[future-r2-integration.md](future-r2-integration.md).
