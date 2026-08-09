# Cloudflare R2 — development bucket setup

**Status of live verification: BLOCKED, not passed.** No R2 credentials were present in
this environment (`backend/.env` carries the `R2_*` keys with empty values, and no `R2_*`
variable was set in the shell). The provider is implemented and unit-tested against a
stubbed S3 client; **no object has ever been written to a real bucket by this code.**
Until someone runs the smoke test in the last section, treat R2 as untested in reality.

Local storage remains the default and is fully functional. Nothing in this document is
required to run the store.

---

## What the application does and does not do

| Does | Does not |
| --- | --- |
| `put_object`, `head_object`, `delete_object` against an existing bucket | Create a bucket |
| Prefix every object it writes with `R2_OBJECT_PREFIX` | Touch anything outside that prefix |
| Refuse a delete for any key outside that prefix | Call the Cloudflare account API |
| Validate the bytes (magic-number sniff) and the size before uploading | Trust the browser-declared content type or file name |
| Store only metadata and the public URL in the database | Store image bytes in the database |

Credentials are read from the environment on the server. They are never sent to React and
never appear in an API response, an error message or the audit log.

---

## 1. Create the bucket in the Cloudflare dashboard

Do this by hand, once. The application deliberately has no bucket-creation code.

1. **R2 → Create bucket.** Name it for this client and this purpose, e.g.
   `vista-store-dev`. Use a *separate* bucket for development; do not share one with
   anything else.
2. **Settings → Public access.** Either enable the `r2.dev` development subdomain, or
   connect a custom domain. Whichever you choose, its URL is `R2_PUBLIC_BASE_URL`.
   Without public access the storefront cannot display an image.
3. **Manage R2 API Tokens → Create API token.**
   * Permission: **Object Read & Write**.
   * Scope it to **that one bucket**. An account-wide token is not needed and should not
     be issued for this.
   * Copy the **Access Key ID** and **Secret Access Key** once — Cloudflare shows the
     secret a single time.
4. Note the **Account ID** from the R2 overview page. The S3 endpoint is derived from it:
   `https://<account-id>.r2.cloudflarestorage.com`.

---

## 2. Configure the backend

Install the optional dependency (only needed when R2 is selected):

```
cd backend
.venv\Scripts\python.exe -m pip install -e ".[r2]"
```

Then set these in `backend/.env`, which is Git-ignored and must stay that way:

| Variable | Required | Meaning |
| --- | --- | --- |
| `STORAGE_PROVIDER` | yes | `r2` to switch over; `local` (the default) to stay on disk |
| `R2_ACCOUNT_ID` | yes | Cloudflare account ID; the endpoint is built from it |
| `R2_ACCESS_KEY_ID` | yes | From the scoped API token |
| `R2_SECRET_ACCESS_KEY` | yes | From the same token — secret |
| `R2_BUCKET_NAME` | yes | The bucket created above |
| `R2_PUBLIC_BASE_URL` | yes | Public base URL, no trailing slash, e.g. `https://pub-xxxx.r2.dev` |
| `R2_OBJECT_PREFIX` | strongly recommended | Namespace for everything this instance writes, e.g. `vista-store/`. **Deletes outside it are refused.** |

```
STORAGE_PROVIDER=r2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_BASE_URL=
R2_OBJECT_PREFIX=vista-store/
```

Leaving any of the first five blank while `STORAGE_PROVIDER=r2` raises
`R2NotConfiguredError` at startup and names exactly which variable is missing — never its
value.

Restart the backend after changing these; the provider is built once per process.

### Object layout

```
<R2_OBJECT_PREFIX><caller prefix><32 hex chars><extension>

vista-store/vista-store/preview/9f6dc75df6a64bb0b5c99ed3836864e9.png   preview import
vista-store/3b4a7b30ba494925afeb0870d6c5951e.jpg                       Admin upload
```

Keys are random, so a caller's file name is never reused and two uploads cannot collide.
The preview importer passes `vista-store/preview/` as its caller prefix, which is what
lets `vista-preview purge` remove exactly its own objects and nothing else.

### Switching an existing instance

Objects already on local disk are **not** migrated. After switching, old media rows keep
their `/media/...` URLs and stay served from disk; new uploads go to R2. Deleting a media
asset deletes the stored object only when the running provider is the one that wrote it —
otherwise the row goes and the file is left where it is, which is the safe way round.

---

## 3. Live smoke test — run this before trusting R2

With credentials in place, from `backend/`:

```
.venv\Scripts\python.exe -c "
from app.core.config import Settings
from app.storage import build_storage
from app.services.placeholder_image import gradient_png
import urllib.request

s = build_storage(Settings())
print('provider:', s.name, 'prefix:', s.object_prefix)

data = gradient_png(64, 64, (91, 62, 133), (228, 179, 60))
stored = s.save(data, content_type='image/png', extension='.png', prefix='smoke-test/')
print('1. uploaded:', stored.key, stored.size_bytes, 'bytes')

print('2. exists:', s.exists(stored.key))

with urllib.request.urlopen(stored.url) as r:
    print('3. public URL:', r.status, r.headers.get('Content-Type'), len(r.read()), 'bytes')

s.delete(stored.key)
print('4. deleted')
print('5. exists after delete:', s.exists(stored.key))
"
```

Expected: `2.` prints `True`, `3.` prints `200 image/png 
<size>`, and `5.` prints `False`. Nothing in that output contains a credential.

Then confirm the refusal that matters:

```
.venv\Scripts\python.exe -c "
from app.core.config import Settings
from app.storage import build_storage
s = build_storage(Settings())
try:
    s.delete('some-other-tool/backup.zip')
    print('FAIL: an out-of-prefix delete was allowed')
except Exception as exc:
    print('OK, refused:', type(exc).__name__)
"
```

Record the result in `docs/implementation-status.md`. If any step fails, R2 stays
**blocked** — do not report it as verified.

---

## 4. Preview media on R2

Once R2 is configured, the preview import uploads through it with no further changes:

```
vista-preview seed        # uploads 12 objects under vista-store/preview/
vista-preview status      # "media stored in  r2"
vista-preview purge       # dry run; lists the objects it would delete
vista-preview purge --confirm
```

`purge` deletes an object only when its key sits inside the batch prefix **and** the
running provider is the one recorded on the media row. Anything else is reported as
skipped, with the reason, and left alone.

---

## Security notes

* `backend/.env` is Git-ignored. Never commit a token; if one is committed, roll it in the
  Cloudflare dashboard rather than deleting the commit.
* Use a bucket-scoped token, not an account-wide one.
* Development and production must use different buckets and different tokens.
* Failures are re-raised as `R2StorageError` carrying only the operation and the exception
  class — never a key, a secret or a signed URL.
* React receives no R2 configuration of any kind. Only the resulting public URL reaches the
  browser, exactly as with local storage.
