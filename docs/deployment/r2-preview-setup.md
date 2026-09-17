# Cloudflare R2 media setup

R2 is Tara's production media provider. The historical filename is retained to keep
existing documentation links stable. LocalStorageProvider remains for development/tests.
Browser uploads go through FastAPI; browsers receive public URLs, never R2 credentials.

## Configuration

Production dependencies include both extras. From `backend/`:

```bash
pip install -c constraints.txt ".[mysql,r2]"
```

Use [the production environment template](../../deployment/env/backend.env.example).
Fill these blanks privately in untracked `backend/.env`:

```dotenv
STORAGE_PROVIDER=r2
R2_ENDPOINT_URL=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_BASE_URL=
R2_REGION=auto
R2_OBJECT_PREFIX=tara-store/
```

The S3 endpoint is normally `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`; it is
backend-only. Use a Tara-only bucket and object-read/write credentials scoped to it.
The application refuses deletes outside its configured prefix; credentials must also
isolate Tara from other projects. Never apply a bucket-wide cleanup to a shared bucket.

`R2_PUBLIC_BASE_URL` is the public media origin, preferably Tara's custom media domain.
Cloudflare documents `r2.dev` as a rate-limited testing endpoint, not production hosting:
[public bucket guidance](https://developers.cloudflare.com/r2/buckets/public-buckets/).
Public URLs come directly from this origin; production Nginx has no local `/media` alias.

Keep stored object keys and URLs stable. Existing `MediaAsset.stored_key` values and
product/order references are not automatically converted by setting `tara-store/` or changing
the public origin. Audit existing keys/URLs before deployment; arrange a separate,
backed-up compatibility plan if they use local `/media`, another prefix or testing URLs.
Do not rewrite historical orders or delete existing objects as part of configuration.

Missing required settings fail clearly. Local development with `STORAGE_PROVIDER=local`
needs no R2 credentials or S3 dependency; its uploads remain ignored runtime data.

## Separately authorized smoke test

Use an isolated disposable Tara test environment and a test bucket/prefix, never
another project's objects. Upload an image through Admin, verify its Content-Type and
stored key under the configured prefix, open its public URL, select it with a Media
Picker, restart and check persistence. Rename its display filename and verify the
stored key is unchanged. Delete only the exact disposable test asset through Admin;
confirm other objects remain. This repository audit does not perform live operations.

No R2 upload CORS rule is needed for Browser -> FastAPI -> R2 uploads and ordinary
public image reads. Future browser-side storage requests would need a reviewed rule.
See [backup and restore](../backup-and-restore.md) for matched database/object backups.
