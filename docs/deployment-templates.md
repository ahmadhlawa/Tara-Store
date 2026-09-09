# Deployment template usage

`deployment/` holds **inactive examples**. Nothing in this repository deploys itself, and
no file in `deployment/` is read by the application at runtime.

These templates were written and reviewed locally. **They have never been installed or
executed on any server.** Treat them as a reviewed starting point, not a proven
configuration.

The operational checklist lives next to the files, in
[`deployment/README.md`](../deployment/README.md). This page explains what each template
does and why it is shaped the way it is.

## Files

```
deployment/
  README.md                                    placeholders, naming, checklist
  systemd/commerce-CLIENT_SLUG.service.example FastAPI under Uvicorn
  nginx/commerce-CLIENT_SLUG.conf.example      SPA + /api proxy + /media
  env/backend.env.example                      pointer to backend/.env.example
```

## Placeholders

Only four, in every file:

| Placeholder | Meaning | Example |
| --- | --- | --- |
| `CLIENT_SLUG` | Short lowercase client identifier | `northwind` |
| `CLIENT_DOMAIN` | Public domain for the storefront | `shop.example.com` |
| `BACKEND_PORT` | Loopback port for this instance | `8001` |
| `PROJECT_PATH` | Absolute path of the instance checkout | `/srv/commerce/northwind` |

Verify none survive before installing anything:

```bash
grep -rn "CLIENT_SLUG\|CLIENT_DOMAIN\|BACKEND_PORT\|PROJECT_PATH" <the copied file>
```

## The systemd unit

Runs Uvicorn as a dedicated unprivileged user, bound to `127.0.0.1:BACKEND_PORT`. Nginx is
the only public entry point; the application is never exposed directly.

Decisions worth preserving:

- **`EnvironmentFile`, not `Environment=`.** Secrets stay in a mode-600 file owned by the
  service user instead of appearing in the unit and in `systemctl show` output.
- **`--proxy-headers` with `--forwarded-allow-ips 127.0.0.1`.** The client IP is taken
  from headers only when the request genuinely came from the local reverse proxy.
- **`ProtectSystem=strict` plus a narrow `ReadWritePaths`.** The only writable path is
  `PROJECT_PATH/backend/data`, which covers uploaded media and — if the instance still
  uses SQLite — the database file. If you move either, update `ReadWritePaths` or writes
  will fail with a permission error that looks like a bug.
- **`Restart=on-failure`.** A crash restarts; a clean shutdown stays down.

## The Nginx site

Serves three things.

**1 — The built SPA**, from `PROJECT_PATH/frontend/dist`:

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

This fallback is not optional. Storefront routes such as `/product/<slug>`, `/cart`,
`/track-order` and every `/admin/*` path are client-side; without it, reloading any of
them returns 404. It is the single most likely thing to get wrong.

Hashed assets under `/assets/` are cached for a year and marked immutable; `index.html` is
explicitly not cached, or returning visitors would pin an old asset manifest.

**2 — The API**, reverse-proxied to the loopback service, with `X-Forwarded-*` set.
`/health` is proxied separately and excluded from the access log.

**3 — Uploaded media**, served directly from disk:

```nginx
location /media/ {
    alias PROJECT_PATH/backend/data/uploads/;
}
```

This path matches production `LOCAL_MEDIA_ROOT=./data/uploads`. Nginx serves the files;
the API never streams them. Script extensions are denied inside that location as a second
layer behind signature checks and Pillow decoding/verification on upload.

If the instance later moves to Cloudflare R2, media URLs point elsewhere and this location
should be removed — see [future-r2-integration.md](future-r2-integration.md).

`client_max_body_size` should sit at or slightly above `MAX_UPLOAD_SIZE_BYTES` so an
oversized upload is rejected by the application, with the standard error shape, rather
than by Nginx with a bare HTML 413.

## The environment pointer

`deployment/env/backend.env.example` deliberately does **not** duplicate the key list.
`backend/.env.example` is authoritative; a second copy would drift. The pointer file
carries only the per-instance deployment notes: set `APP_ENV=production`, generate a unique
`SECRET_KEY`, point `DATABASE_URL` at this client's own database, set `CORS_ORIGINS` to the
real domain, leave `R2_*` and `INITIAL_ADMIN_*` empty, and `chmod 600` the result.

## What these templates do not do

They do not provision DNS, issue certificates, configure a firewall, install a database
server, create system users, or set up backups. Application rate limits are configured
through the backend environment.

## Related

- [new-client-checklist.md](new-client-checklist.md) — cloning the template per client
- [backup-and-restore.md](backup-and-restore.md) — what to back up and how to verify it
- [known-limitations.md](known-limitations.md) — what is missing or untested
