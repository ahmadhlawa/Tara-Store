# cPanel handoff — Tara Store

**Status:** Current deployment handoff template; no production deployment has occurred.

This separates what is finished from what is waiting on someone else. Read the three
sections in order; do not skip to section 3.

---

## 1. Done and verified locally

| Area | State |
| --- | --- |
| Dedicated Tara Store repository | Current source is maintained on `master` |
| Tara Store identity | Applied from `instance/tara-store.yaml` |
| Backend | FastAPI + SQLAlchemy + Alembic, three migrations, MySQL-portable column types throughout |
| Storefront | React/Vite, Arabic, RTL, guest checkout, no customer accounts |
| Admin | Full workspace including the new invoice screens |
| Payments | Cash on delivery and manual transfer only; no card UI; the backend rejects anything else with 422 |
| Invoicing | Automatic on first confirmation, immutable snapshot, sequential numbering, cancellation preserved, browser-printable A4 Arabic sheet |
| Media | Local disk, Tara-specific development root, Git-ignored, collision-resistant filenames |
| Tests | Backend 193 passed (91% coverage), frontend 47 passed, production build clean |
| Local acceptance | 26/26 live checks against a real server — `docs/client/local-acceptance.md` |
| Release packaging | `scripts/make_release_package.py` builds a secret-free archive |

**Also true:** no production system, SSH session, cPanel, MySQL server or R2 bucket was
contacted.

---

## 2. Blocked on the hosting provider

**Nothing about the deployment can be finalised, and no deployment step has been taken.**

Send `cpanel-capability-checklist.md` and wait for the answers. The three that decide
whether this is even possible:

1. Is **Setup Python App** available, and does it offer **Python 3.12+**?
2. Does the host support **ASGI**, or allow a **long-lived uvicorn process**?
3. Is there a **persistent writable directory** that survives deployments?

If (1) or (2) is a no, this application does not run on the account as it stands, and the
conversation becomes about hosting rather than about code. If (3) is a no, product images
vanish on every deploy and we must move media to object storage before launch.

### Values needed once the answers arrive

| Value | Goes into |
| --- | --- |
| MySQL host, database, user, password | `DATABASE_URL` in the backend env |
| Application root path | Python App configuration |
| Document root for the domain | Where `frontend/dist` is published |
| Persistent media path | `LOCAL_MEDIA_ROOT` |
| Public media URL | `LOCAL_MEDIA_BASE_URL` |
| Final domain | `CORS_ORIGINS`, and the instance profile's `domain.primary` |

`deployment/cpanel/backend.env.example` is the template. It ships with every secret blank.

---

## 3. Blocked on the client

The store **cannot take a real order today**, regardless of hosting. It has no delivery
area, so the checkout form cannot be completed; no catalog; and no contact number.

See `docs/client/data-needed-from-owner.md` — 35 items, with 1–8 marked blocking.

Two deserve early attention because they are expensive to change later:

- **Currency.** The configured currency must be confirmed by the Tara Store owner. An
  invoice is an immutable record; one issued in the wrong currency cannot be corrected in
  place, only cancelled and reissued.
- **Invoice prefix.** Defaults to `INV`. Settle it before the first confirmed order, or
  the ledger ends up with two visually different series.

And do not fill the legal or tax fields without written confirmation from the owner. A
wrong registration number printed on a customer invoice is a legal problem.

---

## What we are deliberately not doing

**No Passenger or WSGI adapter has been written.** Writing one before knowing whether the
host needs it — and what shape it needs — would produce a file nobody has tested against
the real environment, which is worse than no file.

**No server-side PDF generation.** Printing is done by the browser, which needs nothing
installed. If the owner later wants emailed PDFs, that is a separate piece of work and it
depends on capability answers A1–A7.

**The release package is not certified deployable.** `make_release_package.py` produces a
correct, secret-free archive of the right files. Whether those files *run* on this
particular cPanel account is exactly the open question. Do not tell the client it is
ready to upload until the checklist comes back.

---

## Deployment outline — provisional, do not execute yet

Written down so the shape is agreed, not so it can be run today. Every step assumes
answers that do not exist.

1. Confirm capabilities. **Stop here if A1/A2/A4 fail.**
2. Create the MySQL database and user; note the forced `cpuser_` prefix.
3. Create the Python app; set the application root and Python version.
4. Build the package: `python scripts/make_release_package.py`.
5. Upload and extract outside the document root if the host permits it.
6. Install dependencies (`pip install -c constraints.txt -r requirements.txt`).
7. Write the real `.env` from `backend.env.example`. **Never commit it.**
8. `alembic upgrade head` against MySQL.
9. `python -m scripts.instance_cli apply --profile instance/tara-store.yaml`.
10. Create the owner's admin account with `python -m app.initial_data`. Delete the local
    development admin; it must never exist in production.
11. Publish `frontend/dist` to the document root.
12. Point `/api`, `/media` and `/health` at the backend.
13. Enable AutoSSL and force HTTPS.
14. Verify against `docs/client/local-acceptance.md`, on the live instance.

Step 8 is the first irreversible one. Take a backup before it.
