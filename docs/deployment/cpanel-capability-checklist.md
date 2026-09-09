# cPanel capability checklist — Tara Store

**Status: unanswered. Send this to the hosting provider or the account owner.**

We do not know whether this application can run on the client's cPanel account. cPanel
plans differ enormously: some run Python apps happily, some are PHP-only, and some allow
Python but not the long-lived ASGI process a FastAPI backend needs. Nothing in the
deployment plan can be finalised until the answers below come back.

Please answer every question, even with "I don't know" — that is itself useful.

## A. Python application hosting — decides whether this is possible at all

| # | Question | Answer |
| --- | --- | --- |
| A1 | Is **Setup Python App** (or Application Manager) present in cPanel? | |
| A2 | If yes, which **Python versions** are offered? We need **3.12 or newer**. | |
| A3 | Which **Passenger** version backs it, if shown? | |
| A4 | Does the host support **ASGI**, or only WSGI? FastAPI is ASGI-native. | |
| A5 | May we run a **long-lived process** (uvicorn/gunicorn) on an internal port and reverse-proxy to it? | |
| A6 | Is there a **process/RAM limit** per account, and what is it? | |
| A7 | Are processes **killed when idle**, and after how long? | |

**A1, A2 and A4 are the decision points.** If Python is absent, or capped below 3.12, or
strictly WSGI with no long-lived process allowed, then FastAPI cannot be deployed to this
account as it stands and we must discuss a VPS or a Python-friendly host instead.

## B. Shell access

| # | Question | Answer |
| --- | --- | --- |
| B1 | Is **Terminal** available inside cPanel? | |
| B2 | Is **SSH** available? On which port, and with a key or a password? | |
| B3 | Can we run `pip install` from a shell? | |
| B4 | Is outbound internet allowed so `pip` can reach PyPI? | |

If neither B1 nor B2 exists, dependencies must be installed through Setup Python App's
own interface, and migrations must be run some other way. Say so and we will plan for it.

## C. Database

| # | Question | Answer |
| --- | --- | --- |
| C1 | Is **MySQL Database Wizard** available? | |
| C2 | MySQL/MariaDB **version**? | |
| C3 | Database **host** — `localhost`, `127.0.0.1`, or a separate hostname? | |
| C4 | Is the account's database-name **prefix** forced, e.g. `cpuser_`? | |
| C5 | Any limit on database count or size? | |
| C6 | Is **phpMyAdmin** available for verification and restores? | |
| C7 | Default character set — is **utf8mb4** available? Arabic content requires it. | |

## D. Application layout

| # | Question | Answer |
| --- | --- | --- |
| D1 | Full path of the account's **home directory**? | |
| D2 | Must the **application root** sit under `public_html`, or may it live outside it? | |
| D3 | What **startup file** and entry-point name does the host require, e.g. `passenger_wsgi.py` with an `application` object? | |
| D4 | Can environment variables be set through the Python App UI, or only through a file? | |
| D5 | Is a `.htaccess` reverse proxy to an internal port permitted? | |

D2 matters for security: the backend source, the `.env` and the Alembic scripts must not
be reachable over HTTP. If everything is forced under `public_html`, we need to agree on
protection rules before anything is uploaded.

## E. Static files and uploads

| # | Question | Answer |
| --- | --- | --- |
| E1 | **Document root** for the target domain? | |
| E2 | Which directories stay **writable and persistent** across deployments? | |
| E3 | Are uploads wiped by any host-side deployment or backup process? | |
| E4 | **Maximum upload size** (`upload_max_filesize` / `post_max_size` equivalents)? | |
| E5 | Disk quota for the account? | |

E2 is critical. Product images are stored on local disk. If the only writable directory
is wiped on each deploy, every product image disappears and we must move to object
storage before launch.

## F. Domain and TLS

| # | Question | Answer |
| --- | --- | --- |
| F1 | Exact **domain or subdomain** for the store? | |
| F2 | Is it already pointed at this cPanel account? | |
| F3 | Is **AutoSSL / Let's Encrypt** available and active? | |
| F4 | Can HTTPS be **forced** for the whole site? | |

## G. Scheduled tasks and mail

| # | Question | Answer |
| --- | --- | --- |
| G1 | Are **Cron Jobs** available, and what is the minimum interval? | |
| G2 | Is outbound **email** available for order notifications, and through which method? | |

## H. Backups

| # | Question | Answer |
| --- | --- | --- |
| H1 | Does the host take automatic backups? How often, and how far back? | |
| H2 | Can we download a full account backup ourselves? | |

---

## What happens with each answer set

**Python 3.12+ with ASGI or a long-lived process, plus shell access** — the normal path.
We finish the deployment package and schedule a release.

**Python 3.12+ but WSGI-only, no long-lived process** — needs an ASGI-to-WSGI bridge.
This is a real code change with real risk, and it will not be written speculatively; it
requires its own scope and testing.

**No Python, or Python older than 3.12** — this application cannot run on the account.
The options are a different hosting plan, a small VPS, or a Python-capable platform. This
is a conversation to have with the owner, not a problem to engineer around.

Until these answers arrive, no deployment step has been performed and none has been
assumed. See `cpanel-handoff.md` for exactly what is and is not ready.
