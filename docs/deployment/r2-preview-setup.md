# Cloudflare R2 media setup

R2 is an optional backend storage provider. Browser uploads always go through FastAPI;
the browser receives only the public asset URL and never R2 credentials.

## Configuration

Install the optional client once in the backend virtual environment:

```powershell
cd D:\Project\Tara-Store\backend
.venv\Scripts\python.exe -m pip install -e ".[r2]"
```

Copy the values below into the untracked `backend/.env` file. Do not put them in a
frontend environment file, source control, logs, or `instance/tara-store.yaml`.

```dotenv
STORAGE_PROVIDER=r2
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<bucket-scoped-object-read-write-access-key>
R2_SECRET_ACCESS_KEY=<secret>
R2_BUCKET_NAME=tara-store-media
R2_REGION=auto
R2_PUBLIC_BASE_URL=https://pub-b26b53198aca49498d03f256874d88c7.r2.dev
R2_OBJECT_PREFIX=tara-store/
```

`R2_ENDPOINT_URL` is used only by the backend S3 client. `R2_PUBLIC_BASE_URL` builds
browser URLs and can later change to `https://media.<TARA_DOMAIN>` without code changes.
Keep the configured prefix stable: random immutable object keys are stored in
`MediaAsset.stored_key`; `original_filename` remains the catalog lookup name.

If R2 is selected and a required setting is blank, the storage provider raises a clear
configuration error. `STORAGE_PROVIDER=local` remains the default and needs no R2
dependency, credentials, or network access.

## Owner smoke test

1. Add the settings above to `backend/.env`, then start the backend normally.
2. Sign into Tara Admin and open **Media Library**. Upload one disposable image.
3. In Cloudflare R2, confirm an object appears in `tara-store-media` under
   `tara-store/` and its metadata has the image Content-Type.
4. Confirm the asset appears in the library and its URL starts with the configured
   `R2_PUBLIC_BASE_URL`; open it in a browser and confirm it renders.
5. Search for its original filename. Rename it in the library, search for the new name,
   and confirm its `stored_key` and the R2 object key did not change.
6. Open a Media Picker from an image field and select that asset.
7. Upload two additional disposable images through the multi-file uploader.
8. Restart the backend and confirm all three public URLs still render.
9. Delete one asset in Admin. Confirm its object is removed from R2; the other two
   objects must remain. Delete the remaining test assets through Admin, or delete only
   their exact `tara-store/` object keys in R2.

No R2 bucket CORS rule is required: uploads use Browser -> FastAPI -> R2 and public
images are normal browser reads. If a future architecture makes browser-side R2 requests,
add a narrowly scoped rule for Tara's actual origins and required methods then.
