# Backend-only automatic translation

Admin remains Arabic-only. There are no English drafts, translation buttons,
review controls, manual translation endpoints, or bilingual save payloads.

The existing storefront architecture is unchanged: Arabic source columns,
English rows in migration `0025_translations`, static frontend dictionaries,
`/ar` and `/en`, RTL/LTR, cart identity, routes, query strings and hashes.
Public browsing reads stored DB translations only and never calls LibreTranslate.

## Automatic flow

1. Admin saves Arabic normally. Allowlisted source changes stage pending English
   work in the same DB transaction; no provider call occurs in that transaction.
2. After commit the backend worker wakes, claims queued rows using durable leases,
   and calls the shared internal LibreTranslate service AR → EN outside DB transactions.
3. Successful results become ready stored English. Source-hash/status/attempt
   comparisons reject obsolete results after subsequent edits or deletions.
4. Provider failures never fail the Arabic save. Work remains failed/retryable
   with exponential backoff (30 seconds to one hour); English browsing falls back
   to Arabic until the current source has a ready translation.
5. Unchanged ready translations remain untouched. Changed sources retain old
   English text while pending/failed, but it is not served until retranslated.
   Existing text does not prevent processing changed or failed work.

## Backend environment

```dotenv
LIBRETRANSLATE_URL=http://127.0.0.1:5000
LIBRETRANSLATE_API_KEY="" # Leave empty unless the service requires authentication.
TRANSLATION_ENABLED=true
TRANSLATION_TIMEOUT_SECONDS=15
TRANSLATION_POLL_SECONDS=30
TRANSLATION_BATCH_SIZE=20
```

These variables are backend-only. The worker starts/stops with the API lifespan
when enabled; disabling it does not prevent source saves or stored translation
reads. Persisted work resumes after restart. Each API process has one poller;
leases prevent duplicate claims. Calls preserve paragraph boundaries/numeric
tokens and use the LibreTranslate adapter with no paid fallback.

Optional operator backfill/retry, from the backend environment:

```bash
python -m app.cli.translate_content --queue-only
python -m app.cli.translate_content --retry --batch-size 20 --max-batches 1
```

No migration rewrite, automatic bulk backfill, or database reset is required.
The [shared private service configuration](deployment/libretranslate.md) remains
independent of Tara; models persist in its Docker volume. No service is deployed
by these changes.

## Files changed to restore automatic translation

Existing storefront code, translation model, migration and shared Compose
configuration are not edited.

- `backend/.env.example`
- `backend/app/main.py`
- `backend/app/services/translations.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/endpoints/admin_catalog.py`
- `backend/app/api/v1/endpoints/admin_commerce.py`
- `backend/app/api/v1/endpoints/admin_content.py`
- `backend/app/schemas/catalog.py`
- `backend/app/schemas/marketing.py`
- `backend/app/schemas/store.py`
- `backend/tests/test_translations.py`
- `frontend/src/api/adminApi.js`
- `frontend/src/admin/ResourceScreen.jsx`
- `frontend/src/admin/pages/CatalogScreens.jsx`
- `frontend/src/admin/pages/CommerceScreens.jsx`
- `frontend/src/admin/pages/ProductEditorPage.jsx`
- `frontend/src/admin/pages/SettingsPage.jsx`
- `frontend/src/test/adminTranslations.test.jsx`
- `docs/localization.md`
- `docs/deployment/libretranslate.md`

Removed:
- `backend/app/api/v1/endpoints/admin_translations.py`
- `backend/app/schemas/translations.py`
- `frontend/src/admin/TranslationField.jsx`
