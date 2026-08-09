# Tara Store fork notes

- Created: 2026-08-09
- Source: `D:\Project\vista-store-e-commerce` at `0589a945ba454b9a53af519ce35b2e4f996a950c`
- Destination: `D:\Project\Tara-Store` (new Git repository; no remote)
- Excluded: Git metadata/history, `.env*`, environments, dependencies, builds, logs,
  test artifacts/screenshots, SQLite databases/backups, generated catalog data, Vista
  profiles, demo data, orders, invoices, administrators, media rows, and uploaded or
  brand media files.
- Development identity: `Tara Store`, slug `tara-store`, SQLite
  `backend/data/tara_store_dev.db`; Alembic head is `0010_unique_media_filename`.
- Media: independent ignored root `backend/data/tara-uploads/`; R2 remains unconfigured.
- Bootstrap creates only instance metadata, Tara store settings, generic home-section
  structure, and blank static-page structure. It creates no catalog, orders, invoices,
  media, coupons, delivery areas, or administrators.

## Branding follow-up

Use Admin Store Settings and Media Library for logo, favicon, store name, contact data,
social links, WhatsApp, and SEO. Replace the inherited visual palette and layout tokens
in `frontend/src/styles/public/tokens.css`, `base.css`, `shell.css`, and `home.css`;
replace the fallback artwork/color handling in `frontend/src/services/storefront.js`.
Populate hero slides and banners through Admin rather than hardcoding them.

## Verification

- Profile validation and application succeeded; database reached Alembic head.
- Empty-data counts verified for products, categories, orders, invoices, media assets,
  coupons, delivery areas, and administrators.
- Backend health: `http://127.0.0.1:8002/health` returned 200.
- Storefront `/` and `/admin/login` returned 200 on `http://127.0.0.1:5176`.
- `adminBackToStore.test.jsx`: 2 passing tests; frontend production build passed.
