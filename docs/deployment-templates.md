# Production deployment templates

Current architecture: MySQL + Cloudflare R2, static SPA, FastAPI/systemd behind Nginx,
and an existing shared private LibreTranslate service. The preparation guide is
[deployment/README.md](../deployment/README.md). These examples are not installed.

| Template | Purpose |
| --- | --- |
| [Environment](../deployment/env/backend.env.example) | MySQL, R2 and private translation |
| [Systemd](../deployment/systemd/commerce-CLIENT_SLUG.service.example) | Dedicated loopback backend and service user |
| [Nginx](../deployment/nginx/commerce-CLIENT_SLUG.conf.example) | Static build and API/health/SEO proxy |

Substitute `CLIENT_SLUG`, `CLIENT_DOMAIN`, `BACKEND_PORT`, and `PROJECT_PATH`.
The `commerce-` filenames remain the supported instance naming convention.
Allocate unique Tara service/user, port, checkout, database/user, logs and site.
Review changes against all sites before reloading Nginx; never replace another
project's resources or global configuration.

Copy the environment template to private untracked `backend/.env`. Production uses
`STORAGE_PROVIDER=r2`, `R2_REGION=auto`, `R2_OBJECT_PREFIX=tara/`, and
`DATABASE_URL=mysql+pymysql://...`. Fill all required R2 blanks with Tara settings.
See [R2 setup](deployment/r2-preview-setup.md). Media URLs come directly from
`R2_PUBLIC_BASE_URL`; Nginx rejects `/media` and has no local filesystem alias.
Do not automatically rewrite existing media keys or URLs when changing providers.

Use `LIBRETRANSLATE_URL=http://127.0.0.1:5000` and `TRANSLATION_ENABLED=true`.
The [shared service guide](deployment/libretranslate.md) is infrastructure reference,
not a step to repeat during releases. Never expose translation through public Nginx
or bundle its image, models or caches in an application release.

Install from `backend/` with `pip install -c constraints.txt ".[mysql,r2]"`.
Production has no local upload/SQLite directory to make writable. The hardened unit
uses private temporary space and journald. Build the SPA before packaging it.
Certificate paths, ownership, migration privileges and substituted configuration
must be checked on the actual host before separately authorized installation.

Local filesystem media and SQLite in [local setup](local-setup.md) remain intentional
development/test capabilities. See [backup and restore](backup-and-restore.md) and
[known limitations](known-limitations.md) for remaining operational checks.
