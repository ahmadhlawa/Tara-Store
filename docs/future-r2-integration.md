# Future Cloudflare R2 integration

> **Superseded as of `feat/vista-preview-data-storage` (2026-08-02).** The provider is no
> longer a stub: `save()`, `delete()` and a new `exists()` are implemented against R2's
> S3-compatible API, with prefix containment and 25 unit tests. Configuration and the
> live smoke test are in **[deployment/r2-preview-setup.md](deployment/r2-preview-setup.md)**,
> which is now the page to read. What follows describes the boundary and the reasoning
> behind it, and is still accurate on both.
>
> Still true: **no R2 account, bucket or credential has ever been used from this
> repository.** No credentials were available, so the implementation has never written a
> byte to a real bucket. Live R2 is **blocked, not verified.**

**Original status: a deliberate boundary, not an implementation.** Local disk storage is
the only working provider. `R2StorageProvider` exists so that switching a deployed instance
to object storage is a configuration change plus one dependency rather than a refactor —
nothing outside `app/storage/` knows where bytes live.

## The boundary

`app/storage/base.py` defines the whole contract:

```python
class StorageProvider(ABC):
    name: str
    def save(self, data: bytes, *, content_type: str, extension: str) -> StoredFile: ...
    def delete(self, key: str) -> None: ...
    def url_for(self, key: str) -> str: ...
```

`StoredFile` carries `key`, `url`, `content_type` and `size_bytes`.

Provider-independent logic already lives in `base.py` and is shared by every
implementation:

- `validate_image_upload()` — rejects empty files, enforces `MAX_UPLOAD_SIZE_BYTES`, and
  identifies the type from **magic bytes** rather than the client-declared content type or
  filename
- `build_stored_key()` — `uuid4().hex` plus the canonical extension, so the caller's
  filename is never reused. That is what makes stored names collision-resistant and
  immune to path traversal

An R2 implementation therefore inherits validation and naming for free; it only moves
bytes.

`app/storage/__init__.py` selects the provider from `STORAGE_PROVIDER` and caches it.
Endpoints call `get_storage()` and never branch on which provider is active.

## Current behaviour

`STORAGE_PROVIDER=r2` with missing variables raises `R2NotConfiguredError` listing exactly
which are absent — a loud failure at construction rather than a silent fallback to local
disk. With all five present, `save()` and `delete()` still raise, because they are not
implemented. `url_for()` already returns `{R2_PUBLIC_BASE_URL}/{key}`.

The database stores metadata and a URL, never bytes, so switching providers does not
require a schema change.

## Implementing it

**1 — Dependency.** Add `boto3` to `backend/pyproject.toml`. R2 is S3-compatible, so no
Cloudflare-specific SDK is needed.

**2 — Client.** Build one against the R2 endpoint:

```python
session = boto3.session.Session()
client = session.client(
    "s3",
    endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=self.access_key_id,
    aws_secret_access_key=self.secret_access_key,
    region_name="auto",
)
```

Create it once per provider instance, not per request.

**3 — `save()`.** `put_object` with `Bucket`, `Key`, `Body` and `ContentType`, then return
`StoredFile(key=key, url=self.url_for(key), content_type=..., size_bytes=len(data))`.
Do **not** set a public-read ACL; R2 serves public objects through a public bucket URL or
a custom domain, which is what `R2_PUBLIC_BASE_URL` is for.

**4 — `delete()`.** `delete_object`. Treat a missing key as success — deletion must be
idempotent, since the media endpoint deletes the row and the object together.

**5 — Errors.** Wrap `botocore` exceptions in a `DomainError` so failures reach the client
in the standard `{"error": {...}}` shape instead of surfacing as a 500.

**6 — Configuration.**

```
STORAGE_PROVIDER=r2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_PUBLIC_BASE_URL=https://media.CLIENT_DOMAIN
```

Credentials belong in the instance `.env` (mode 600), never in the repository. One bucket
or one prefix per client instance — never a shared bucket across clients.

**7 — Nginx.** When R2 is active, the `/media` location that serves files from disk is no
longer needed; media URLs point at `R2_PUBLIC_BASE_URL` instead. Remove or bypass it so
stale local files cannot shadow object storage.

**8 — Tests.** Existing storage tests cover the local provider. Add tests for the R2
provider with a stubbed client — assert the key shape, the content type, idempotent
delete, and that a `botocore` failure becomes a `DomainError`. Do not add a test that
requires real credentials.

## Migrating existing media

For an instance already running on local disk:

1. Upload every file from `LOCAL_MEDIA_ROOT` to the bucket, preserving the stored
   filenames exactly — the database references them.
2. Rewrite `media_assets.url` and any `product_images.url` from the old base URL to the
   new one, in one transaction.
3. Switch `STORAGE_PROVIDER` and restart.
4. Keep the local directory until the URLs have been verified in a browser; then archive
   it rather than deleting it.

Do **not** rename files during the move. The stored name is the join key between the
object and the database row.

## Trade-offs to weigh first

- Local disk means media is included in a filesystem backup and served by the same Nginx
  that serves the app. R2 means backup and restore become two separate procedures — see
  [backup-and-restore.md](backup-and-restore.md).
- R2 removes disk-space limits and adds egress-free CDN delivery, which matters for image
  heavy stores.
- For a single-instance store with modest traffic, local disk is genuinely adequate. Move
  when there is a reason — disk pressure, multiple app servers, or a CDN requirement — not
  by default.
