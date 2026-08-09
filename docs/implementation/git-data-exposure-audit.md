# Git data exposure audit and history remediation

Five whole SQLite database files were committed to this repository and pushed to
GitHub. This document records what they contained, how far the exposure reached,
what was done about it, and what is still outstanding.

It contains no credentials, no database contents, and no personal data. Every
classification below was produced by counting rows and inspecting column shapes,
never by printing stored values.

Date of remediation: 2026-08-05.

---

## 1. What was exposed

Four `.bak` files and one `.db` file. The four `.bak` paths share three distinct
blobs, because two of them are byte-identical copies of the same database.

| Path | Blob | Size | Introduced by |
| --- | --- | --- | --- |
| `backend/data/vista_preview.20260802-192413.bak` | `4b9e2c89` | 385,024 | `fe96854` |
| `backend/data/vista_preview.db.20260804-051436.bak` | `8995b2da` | 413,696 | `c9d6b1e` |
| `backend/data/vista_store_dev.20260802-192413.bak` | `5039c69d` | 331,776 | `fe96854` |
| `backend/data/vista_store_dev.db.20260804-051436.bak` | `5039c69d` (shared) | 331,776 | `c9d6b1e` |
| `backend/data/commerce_dev.db` | `904beeb7` | 344,064 | `0c6ff5de` |

`commerce_dev.db` was found during this audit and was not part of the original
report. It had been deleted from the working tree by `dba6a67a` long before, but
deleting a file does not remove it from history, and it remained reachable from
every branch and tag in the repository.

### Contents

Every one of the five files is a complete SQLite database containing:

- one `admin_users` row, with an email address and a password hash,
- order rows with customer names, phone numbers and delivery addresses,
- invoice rows with the same customer fields plus delivery area,
- `orders.public_token` capability tokens,
- store settings, catalog, media and audit rows.

### Severity: development and demo data, not confirmed real customer data

This matters for how urgently the remaining server-side cleanup must be chased,
so the reasoning is recorded rather than asserted:

- Every administrator address is on an RFC 2606 reserved domain — `example.com`
  and `vista-store-local.example`. These are non-routable by definition and
  cannot receive mail.
- Passwords are **argon2id hashes**, not plaintext. No JWT, API key, SMTP
  credential, private key or access token was found in any of the five files.
- Across all five databases there are **11 order rows in total**. Nine carry
  phone numbers with repeated or sequential digit runs, and one uses the prefix
  `000` — the signature of seeded fixtures, not of real orders.
- Git history was also scanned for secret-shaped paths. The only matches are
  `.env.example`, `backend/.env.example` and `frontend/.env.example`. No real
  `.env` file, keystore or private key has ever been committed.

The classification is therefore **local development/demo data exposure**. The
files still had to go: a published argon2id hash is a permanent offline-cracking
target, and the exposure of a live local administrator credential is real
regardless of how synthetic the surrounding order rows are.

---

## 2. How the guards missed it

Two mechanisms should have caught this and both had the same blind spot.

`.gitignore` covered `*.db`, and the CI check in
`.github/workflows/mysql-compatibility.yml` matched `.*\.db$`. The committed
backups are named `vista_preview.db.20260804-051436.bak` — the `.db` is in the
middle of the name, not at the end, so neither rule matched. The CI check also
anchored environment files on `\.env$`, which would not have matched
`.env.mysql.local` either.

`commerce_dev.db` did end in `.db`, but the CI check inspects `git ls-files`,
which reports only the current index. The file had already been deleted from the
working tree, so the guard saw a clean index while the blob stayed reachable in
history.

---

## 3. What was done

### Backups taken first

Two independent mirrors were created outside the repository, before anything was
rewritten. Both were verified to carry every ref and to pass `git fsck --full`.

- `D:\GitSafety\vista-store-before-sensitive-rewrite-20260805-231145.git`
  — mirror of the local repository. Holds `main` at `0a2a0f8`, including the 45
  commits that had never been pushed, plus every remote-tracking ref and all
  five tags.
- `D:\GitSafety\vista-store-before-sensitive-rewrite-20260805-231145-copy.git`
  — mirror of `origin`. Holds `main` at `c9d6b1e`.

These mirrors deliberately still contain the sensitive blobs. That is their
purpose: they are the rollback path. Treat them as sensitive material and delete
them once the remediation is confirmed settled.

### The rewrite

`git filter-repo` (with `--sensitive-data-removal --invert-paths`) was run in a
dedicated mirror clone at `D:\GitRewrite\vista-store-clean.git`, never in the
active development checkout. The mirror was assembled from `origin` and then had
the local `main` and the local-only tags fetched into it, so that the rewrite
covered the complete superset rather than only what had been pushed.

110 of 118 commits were rewritten.

| Ref | Before | After |
| --- | --- | --- |
| `main` | `0a2a0f8` | `6218abf` |
| `feat/vista-preview-data-storage` | `2b536ce` | `79ff5ea` |
| `feat/vista-store-initial-release` | `db16863` | `42f5796` |
| `feat/vista-storefront-rebuild` | `fe96854` | `d3bcbce` |
| `fix/vista-reference-alignment` | `1a05b82` | `f0f929c` |
| `v0.3.0-rc.1` | `2df68de` | `ceeaa7b` |
| `archive/vista-before-repository-rebrand-24ab8b4` | `1104287` | `b13ae7f` |
| `archive/vista-final-998781c` | `8210a70` | `c6eccf4` |
| `backup-main-before-order-invoice-20260805-173713` | `cf32df9` | `0534b14` |
| `archive/frontend-foundation-f2ddd6e` | `f2ddd6e` | unchanged |

**First changed commits**, which GitHub Support asks for:

- `0c6ff5decdfa0d84b5db5bce95e6cf7c1a60a276` → `d117e8add64d72d44613f88f280b13cf6c2af9d0`
- `8260e323ad6125b2e2bfcfb7b6407cd4955c55f3` → `328e9cbeb12e87b9d3fc68adcdbb4427a46c24fa`

### Proof that nothing else was lost

- The tree hash of `main` is **`41bbe06a` before and after** the rewrite, with
  489 files in both. The checked-out content is byte-identical; only history
  metadata changed.
- Per branch: `main`, `feat/vista-preview-data-storage` and
  `feat/vista-store-initial-release` have identical file sets. The two branches
  that held `.bak` files lost exactly those two files and nothing else.
- One commit was pruned: `fe96854`, which added *only* the two `.bak` files and
  so became empty. `dba6a67a`, which deleted `commerce_dev.db` alongside eight
  other artifacts, survives and still removes the other eight.
- A disposable clone of the rewritten mirror was verified independently:
  backend `370 passed, 4 xfailed`; frontend `149 passed`; `vite build` green and
  emitting **identical asset hashes** to the pre-rewrite build; `git status` and
  `git diff --check` clean.

### The push

`origin` was re-checked immediately beforehand and confirmed to be exactly at the
freeze point. A `--dry-run` was inspected first; it listed six forced updates and
no deletions. The push applied exactly those six. No branch protection was
encountered, so no protection rule was weakened or changed.

The three local-only tags were deliberately **not** pushed. They were never on
`origin`, and publishing them would have widened the change beyond the intent.

### The local checkout

The development directory was realigned in place rather than re-cloned, which
preserved `backend/.venv`, `frontend/node_modules`, and the local databases in
`backend/data/`. Because the old and new trees are identical, the branch ref
could simply be moved with `git update-ref` — no `git reset --hard` was used.

Reflogs were then expired and `git gc --prune=now` run. All four sensitive blobs
were confirmed purged from the local object store afterwards.

---

## 4. Still outstanding

### The data is still on GitHub's servers

This is the most important item in this document, and it is verified rather than
assumed. **After** the force-push, a fresh clone of `origin` was made and the old
commit `fe96854` was fetched by SHA:

```
git fetch origin fe96854340ecf7093f9716695e338ee0ae86d384   # succeeded
```

Both sensitive blobs were then retrieved intact — 385,024 and 331,776 bytes.

A force-push rewrites refs; it does not delete unreachable objects. Until GitHub
runs server-side garbage collection, anyone who knows or can guess an old commit
SHA can still download these files, and old SHAs remain visible in any cached
page, notification email, or external reference.

**Do not treat this exposure as closed until GitHub Support confirms the objects
are gone.**

Information needed for the request:

- Repository: `ahmadhlawa/vista-store-e-commerce`
- First changed commits: `0c6ff5de` and `8260e323` (see above for full SHAs)
- Pull requests affected: none observed — `git ls-remote origin 'refs/pull/*'`
  advertises no pull refs
- Git LFS: not in use; `filter-repo` reported no LFS orphaning
- Ask: purge unreachable objects / stale commit SHAs for the listed refs

Forks could not be enumerated: the `gh` CLI is not installed on this machine, and
a fork would keep its own copy of the objects regardless of what happens here.
That should be checked in the GitHub web UI.

### Credential rotation

The administrator in the live local database `backend/data/vista_preview.db` is
`preview-admin@example.com`, and its argon2id hash was verified to be
**byte-identical** to the blob that was published. It should be rotated:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli.reset_admin_password --email preview-admin@example.com
```

If that password was ever reused anywhere else, rotate it there too.

Separately, `frontend/e2e/helpers.js` carries the acceptance password for three
fixture accounts in tracked source. That is intentional — those accounts exist
only inside a disposable validation database and are worthless anywhere else —
but it does mean they are public, and they must never be created in a real
environment.

### Collaborator clones

This is a single-developer repository. `origin` carries five branches and two
tags, and no pull refs are advertised. No other clone is known.

If a clone does exist elsewhere, it must not push: doing so would restore the
deleted objects. Preserve unpushed work as patches, delete the clone, and clone
again from the cleaned `origin`.

---

## 5. Preventing a repeat

`backend/tests/test_repository_hygiene.py` asserts against the Git index that no
database, backup, real environment file or generated directory is tracked. It
runs in the normal backend suite, so it fails on a developer's machine before it
can fail in CI. One of its cases pins the five paths that actually leaked, so the
matcher cannot silently stop covering the case that motivated it.

The CI step in `.github/workflows/mysql-compatibility.yml` now applies the same
pattern, and `.gitignore` covers `*.bak`, `*.dump`, `*.sqlite` and `*.sqlite3`
alongside the existing `*.db` rules.

Both were verified against the real leaked filenames: the old pattern let four of
the five through, the new one catches all five.
