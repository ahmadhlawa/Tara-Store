# Tara first-party analytics

## Metric semantics

- **Session / visit:** starts on first tracked storefront activity. Activity stays in the same session while gaps are under 30 minutes. The next activity after 30 minutes creates a new session.
- **Unique visitor:** a server-generated random first-party `tara_visitor` HttpOnly cookie. The database stores only its HMAC hash. Clearing cookies/incognito/another device can count as a new visitor; there is no fingerprinting.
- **Product view:** a valid PDP view. The same product in the same session is suppressed for 30 seconds to stop refresh inflation. A later revisit can count again; a new session always starts a fresh dedupe scope.
- **Periods:** Today / 7d / 30d use local `Asia/Hebron` calendar midnights and convert each boundary independently to UTC, including DST changes.

## Location trust

Cloudflare city/country/region headers are used only when both:

1. `ANALYTICS_TRUST_CLOUDFLARE_HEADERS=true`; enable this only after Tara's HTTPS origin requires Cloudflare Authenticated Origin Pulls (mTLS), and
2. Nginx overwrites `X-Tara-Analytics-Proxy` with the same long random value configured as `ANALYTICS_PROXY_TOKEN`.

Without both conditions, analytics stores `غير محدد`; it never trusts browser-supplied location data.

Normalization checks explicit known localities first (`القدس`, `عناتا`, `العيزرية`, `حزما`, `الزعيم`), then collapses other `IL` locations to `الداخل`.

## Abuse controls

- Explicitly foreign Origin/Referer is rejected.
- Obvious crawler User-Agents are ignored.
- Application fallback rate limit is intentionally generous (default 1200/min/IP in production).
- Nginx template defines analytics-only 10r/s + burst 120 in **dry-run** mode. Review would-have-limited logs under real CGNAT/shared-IP traffic before enabling enforcement.
- Analytics failures/429s are fire-and-forget in the storefront and never block browsing/cart/checkout.

## Retention

Raw sessions and product views are kept 365 days by default. `tara-analytics-prune` deletes expired rows in bounded batches. Production should enable the supplied systemd timer after deployment.

## AOP monitoring

AOP certificate reminders are necessary but not sufficient. Production must also have a runtime availability monitor:

- external: `https://CLIENT_DOMAIN/health` through Cloudflare
- internal: `http://127.0.0.1:BACKEND_PORT/health`

External failure + internal success points to Cloudflare/AOP/origin TLS. Both failing points to backend/origin. Keep certificate ownership and 60/30/14/7-day renewal reminders in deployment notes.

## Scale threshold

Keep indexed raw queries initially. Re-evaluate rollups when retained product views approach 1,000,000 rows or the 30d summary endpoint sustains p95 > 400ms under normal production load. Preserve the Admin response contract if rollups are added.
