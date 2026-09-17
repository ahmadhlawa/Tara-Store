# Tara Store

Arabic RTL / English LTR e-commerce storefront and administration platform for Tara Store.

> **Project status:** production deployment is pending; owner catalog/data readiness requires handoff verification.

The application provides a public storefront, guest checkout, order tracking, editorial
content, and an administration workspace for catalog, media, orders, promotions, content,
settings, administrators, audit history, and invoices. Cash on delivery and manual payment
are supported; online card payments are not included.

## Platform

| Layer | Technology |
| --- | --- |
| Frontend | React and Vite |
| Backend | FastAPI, SQLAlchemy, and Alembic |
| Local database | SQLite |
| Production database | MySQL 8 compatible |
| Production media | Cloudflare R2 |
| Development media | Local storage (R2 optional) |
| Translation | Shared private LibreTranslate, stored in the database |

The active profile is [Tara Store](instance/tara-store.yaml).

## Local setup

Requires Python 3.12+ and Node.js 22.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev]"
copy .env.example .env
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m scripts.instance_cli apply --profile ..\instance\tara-store.yaml
.venv\Scripts\python.exe -m app.initial_data --email you@example.com --password '<choose one>'
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# In a second terminal
cd frontend
npm ci
npm run dev
```

See [local setup](docs/local-setup.md), [deployment handoff](deployment/README.md),
and [known limitations](docs/known-limitations.md).

## Testing

```powershell
cd backend
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m scripts.mysql_compat --verbose

cd ..\frontend
npm ci
npm test -- --run
npm run build
```

Historical release and architecture records are retained for provenance and are not the
current readiness source.
