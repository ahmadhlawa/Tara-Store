# Vista Store

Arabic RTL e-commerce storefront and administration platform for Vista Store.

> **Project status:** local development only. Nothing has been deployed.

Vista Store provides a public storefront for browsing products, managing a cart, guest
checkout, coupons, delivery areas, order tracking, editorial content, and static pages.
Its admin workspace manages the catalogue, media, orders, coupons, delivery areas, home
content, pages, articles, settings, administrator accounts, audit history, and invoices.

Cash on delivery and manual payment are supported. Online card payments are not included.
An immutable, sequential invoice is created automatically when an order is first confirmed.

## Platform

| Layer | Technology |
| --- | --- |
| Frontend | React and Vite |
| Backend | FastAPI, SQLAlchemy, and Alembic |
| Local database | SQLite |
| Production database | MySQL-compatible |
| Media storage | Local storage or Cloudflare R2 |

The active profile is [Vista Store](instance/vista-store.yaml): `Vista Store` / `متجر فيستا`,
using the verified Vista colour identity and logo. `ILS` / `₪` remains the documented
preview default only; it must be confirmed by the owner before real orders are accepted.

## Local setup

Requires Python 3.12+ and Node.js 18+.

```powershell
cd D:\Project\vista-store-e-commerce\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev]"
copy .env.example .env
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m scripts.instance_cli apply --profile ..\instance\vista-store.yaml
.venv\Scripts\python.exe -m app.initial_data --email you@example.com --password '<choose one>'
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# In a second terminal
cd D:\Project\vista-store-e-commerce\frontend
npm install
npm run dev
```

See [local setup](docs/local-setup.md), [deployment handoff](docs/deployment/cpanel-handoff.md),
and [known limitations](docs/known-limitations.md).

## Testing

```powershell
cd D:\Project\vista-store-e-commerce\backend
.venv\Scripts\python.exe -m pytest

cd D:\Project\vista-store-e-commerce\frontend
npx vitest run
npm run build
```

## Current limitations

- The real owner catalogue is still being finalized.
- Live Cloudflare R2 credentials are pending.
- Production cPanel deployment is pending.
- No online card payment is available.

This client project originated from the internal commerce foundation and is now maintained
as the dedicated Vista Store application. Historical release and architecture records are
retained for provenance; they are not part of the current onboarding path.
