# Local Production mirror

Production continues to use MySQL and R2. Localhost must use its own disposable
MySQL database, `tara_prod_mirror`; it must never connect to Production directly.
This tool operates only on a dump that has already been imported into that local
database. It does not read or write R2 credentials or objects.

## Configure and audit

Run commands from `backend`. Set local environment variables in your shell; do
not change Production settings or commit credentials. Use the local MySQL user's
credential in `DATABASE_URL` and URL-encode special characters in it.

```powershell
$env:APP_ENV = "development"
$env:DATABASE_URL = "mysql+pymysql://<local-user>:<url-encoded-local-password>@127.0.0.1:3307/tara_prod_mirror"
$env:STORAGE_PROVIDER = "local"
$env:LOCAL_MEDIA_ROOT = "./data/tara_prod_mirror_uploads"
$env:LOCAL_MEDIA_BASE_URL = "/media"
python -m scripts.prepare_local_prod_mirror audit
```

Keep all five variables set in the shell used to run the local backend as well
as the mirror tool. Otherwise the backend will not serve mirrored media from
`backend/data/tara_prod_mirror_uploads/`.

Import a fresh Production dump into `tara_prod_mirror` using your existing local
database import process, then sanitize the imported copy:

Stop local API, import, and translation processes while preparing the mirror.

```powershell
python -m scripts.prepare_local_prod_mirror sanitize --execute --confirm-local-mirror
```

Sanitization removes local copies of customer/order, audit, analytics, and
Production admin/login data. Catalog, stock, content, store configuration,
translations, import history, schema revision, and coupon definitions remain;
coupon usage counts reset to zero.

## Mirror media

After sanitation, media can be downloaded read-only from its public HTTPS domain.
The operator-supplied base URL must match each asset's saved URL and key. Files
are stored under `backend/data/tara_prod_mirror_uploads/`; only local database
media references are rewritten. Production R2 remains untouched.

```powershell
python -m scripts.prepare_local_prod_mirror media `
  --source-base-url https://media.the-taragallery.com `
  --execute --confirm-local-mirror
```

`audit` is read-only. `sanitize` and `media` are dry runs unless both execution
flags are supplied. The target must be development MySQL on `127.0.0.1` or
`localhost` at port `3307`, named exactly `tara_prod_mirror`, and at Alembic
head. Port `3306` and URLs without an explicit port are rejected.

## Create a local admin

The mirror deliberately does not retain a Production admin. After sanitizing,
create a fresh local account through the existing initializer:

```powershell
$env:INITIAL_ADMIN_EMAIL = "<your-local-email>"
$env:INITIAL_ADMIN_PASSWORD = "<choose-a-local-password>"
python -m app.initial_data
```

Do not put these values in source control.

## Destroy and recreate

The mirror is disposable. To recreate it, stop local app processes, use your
local MySQL administration tool to drop and recreate only the local
`tara_prod_mirror` database, import a fresh dump into that database, and rerun
the audit, sanitize, media, and local-admin steps above. Do not point these steps
at Production or a remote MySQL server.

For example, using a dump file already on your computer:

```powershell
mysql -h 127.0.0.1 -P 3307 -u <local-user> -p -e "DROP DATABASE IF EXISTS tara_prod_mirror; CREATE DATABASE tara_prod_mirror;"
mysql -h 127.0.0.1 -P 3307 -u <local-user> -p tara_prod_mirror < <local-dump.sql>
```
