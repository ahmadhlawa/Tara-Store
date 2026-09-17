# Backup and restore

Production is **MySQL + R2**. Back up database metadata and its referenced media objects
as a matched recovery set. Local upload folders are not production media storage.
These procedures require separate operational authorization; repository cleanup runs
none of them and must not affect shared server resources.

## Recovery set

| Item | Scope |
| --- | --- |
| MySQL snapshot | Tara's database only: catalog, orders, content, translations, admins |
| R2 object snapshot | Tara's referenced keys under `tara/`, with bytes and metadata |
| Manifest | Timestamp, commit, Alembic revision, database identity, bucket/prefix, object keys and checksums |
| Private environment | Encrypted, separately controlled copy of `backend/.env` |

Use protected credentials and encrypted off-host storage. Retain multiple monitored
recovery generations. Database dumps contain customer records and password hashes;
never commit them, put them in a public bucket or copy them into a release package.
The built frontend and virtualenv are reproducible; record the source/dependency versions.

## Production backup

Arrange a coordinated Tara write pause or equivalent consistency procedure so uploads,
media deletions and database changes cannot make the snapshots disagree. Pause only
Tara's writers, not other applications or the shared LibreTranslate service.

An operator can dump Tara's InnoDB database using `mysqldump --single-transaction
--routines --triggers --default-character-set=utf8mb4` with a protected credentials
file or interactive password prompt. Verify database-specific dump/restore privileges
and a successful exit status. Do not place passwords in command lines or documentation.
Do not change shared MySQL global settings to make a backup or migration work.

Copy the exact Tara object inventory to a private backup destination using a reviewed
S3-compatible backup tool. Preserve full object keys, Content-Type and checksums, and
verify that every database-referenced object is included. Do not assume S3 feature
parity or bucket versioning; use explicit retained object snapshots. Never run a
bucket-wide delete, lifecycle change or destructive sync on a shared bucket.

## Restore rehearsal and recovery

Rehearse into an isolated scratch database and private test storage first. Preserve
production recovery sets unchanged; do not overwrite the working database to test them.

For a separately authorized production recovery, pause only Tara, verify the selected
manifest, restore Tara's database and its exact referenced R2 object set, and ensure
stored public URLs still resolve. Do not delete unrelated objects or rewrite historical
orders. With Tara stopped, reconcile the restored Alembic revision with the selected
application release before restarting; an older database may require forward migrations.

Verify `/health` and `/ready`, expected Alembic revision, order counts/recent snapshots,
translated content, Admin login, store identity and representative image URLs. `/ready`
alone does not make a live R2 request. A changed `SECRET_KEY` signs administrators out.
Never run demo seeding on a restored production store.

The shared LibreTranslate model volume is independent infrastructure. Tara's release
or recovery must not recreate, stop, prune or delete it. Stored translations are in
Tara's MySQL backup; shared service backups belong to its operator.

## Intentionally retained local development workflow

Local SQLite and LocalStorageProvider are development/test capabilities. For an
existing local dataset, use SQLite's backup API rather than copying a file mid-write;
pair `backend/data/tara_store_dev.db` with `backend/data/tara-uploads/` while local
media writes are paused. Keep these files, their WAL/SHM sidecars and backups ignored.
This local workflow does not apply to production.
