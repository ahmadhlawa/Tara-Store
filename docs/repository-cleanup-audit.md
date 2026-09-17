# Pre-deployment repository cleanup audit

Scope: 416 tracked files on `master`, starting from a clean working tree at
`96e4e2f72d03dbe5d61f69f7179411ab421abc8f`. No deployment, server/resource access,
commit, push, migration rewrite, application/business logic or customer-data conversion.

## Deletions and evidence

| Files | Why removal is safe |
| --- | --- |
| Eight PNG files in `footer-samples/` (all tracked `ChatGPT Image Sep 15, 2026` variants) | Design mockups; no filename, directory, runtime, code, test, documentation or build references in the tracked text corpus. Outside build source. |
| `frontend/public/branding/footer/botanical-sprig.png` | No asset/path/directory references; current Footer uses inline icons and the configured logo, without dynamic directory enumeration. Otherwise Vite copies it unnecessarily. |
| `frontend/public/branding/footer/floral-divider.png` | Same reference/runtime/build evidence as botanical-sprig; unused decorative design asset. |
| `deployment/cpanel/backend.env.example` | Abandoned hosting template, superseded by the MySQL/R2/systemd production environment; packaging references replaced first. |
| `docs/deployment/cpanel-capability-checklist.md` | Hosting approach superseded by the user's fixed architecture; current links and release instructions replaced. |
| `docs/deployment/cpanel-handoff.md` | Same obsolete hosting approach; replaced by deployment/README.md and current templates. |
| `docs/future-r2-integration.md` | Describes an inert provider that is now implemented. Current R2 setup is retained and corrected; links updated. |
| `scripts/.gitkeep` | Empty-directory placeholder is redundant with tracked make_release_package.py; no references and no required runtime directory role. |

Reference checks covered imports, static/runtime paths, tests, docs, build configuration
and Git-tracked text. Asset checks included directory fragments to catch constructed
paths. No uncertain source files or old tests were deleted.

## Intentionally retained

- Preview, catalog-prep, cutover, seed and instance tooling: current CLI entrypoints,
  imports and test coverage; no tracked generated customer catalog was found.
- All tests and migration revisions, including legacy Vista fixture names: regression
  evidence and immutable schema history, not runtime customer data.
- Historical plans, acceptance and implementation records: provenance. The running
  implementation log now points to the current production architecture; links to
  absent historical records are explicitly marked rather than pretending to resolve.
- LocalStorageProvider, SQLite tooling, local MySQL Compose, the Tara upload `.gitkeep`
  and brand README: intentionally retained development/test capability and guidance.
- `docs/future-mysql-migration.md` and `docs/deployment/r2-preview-setup.md`: useful
  current operational guidance; filenames retained for CLI/documentation references.
- Branding images/favicon and the empty catalog workbook: each has current references.
- `commerce-CLIENT_SLUG` templates/CLI names: supported instance naming conventions.

## Production alignment and hygiene

Production environment specifies MySQL, R2 with `auto` region and `tara/` prefix,
private loopback LibreTranslate and enabled stored translations. Nginx rejects local
`/media`; systemd grants no local database/upload write directory. Current deployment, local SQLite/fixture,
backup, lifecycle/cutover and readiness guidance reflects MySQL/R2, while local examples
remain explicitly development-only. No real credentials appear in the templates.

Packaging now uses current templates, includes both MySQL/R2 runtime extras, and copies
only the Tara profile, excluding generated customer catalogs. Source CLI modules remain
because pyproject exposes them; their runtime data is excluded. Shared translation
infrastructure/models are never included.

Ignore rules and hygiene tests now cover Tara uploads/validation artifacts, generated
catalogs, SQLite WAL/SHM/journals, SQL/compressed dumps, credentials/private keys and
browser/coverage output. CI reuses the same hygiene tests without loading app fixtures.

## Validation and remaining concerns

Full backend suite: 599 passed, 4 expected failures; frontend: 302 passed across
36 files; production build passed. Focused hygiene/packaging checks: 34 passed.
Git diff --check passed. Changes remain unstaged and uncommitted; no push or deployment.

Static checks found all 504
relative frontend imports and 455 backend project imports resolve. Current local
Markdown links resolve; historical regex/example text is not treated as a file link.
All remaining tracked assets have references. A locally staged 158-file production
package passed its runtime/secret exclusion audit and contains boto3 and PyMySQL[rsa].
A secret scan of the tracked working-tree snapshot found no leaks.

Actual host configuration, permissions, R2 access/custom-domain setup, backup/restore
and shared translation connectivity require a separate operational verification. In
particular, changing R2_OBJECT_PREFIX or its public origin does not migrate existing
stored keys/URLs: inspect existing local-media/testing URLs and prefixes without
rewriting historical orders or deleting objects. No live check or conversion was done.
