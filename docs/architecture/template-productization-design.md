# Template productization — design note

## Problem

The MVP is a working single-store commerce application. Creating a client instance today
means copying the repository and hand-editing store identity through the Admin UI, with
nothing recording which template version an instance came from, and with the only
"initialize a store" path being a demo seed that inserts fake products and orders.

Three things are missing: a declarative, non-secret description of a client instance; a
safe, repeatable way to apply it to a **new empty database**; and traceability from a
running instance back to the template version that produced it.

## Non-goals

No multi-tenancy, no `tenant_id`, no SaaS layer, no plugin framework, no Docker, no
database snapshot cloning, no server provisioning, no MySQL connection. The storefront and
Admin UI are untouched. One running application remains one store.

## Design

### 1. Golden Template version

A single tracked file, `VERSION`, at the repository root holds the template version
(starting at `0.2.0` — pre-1.0, reflecting a functional MVP now gaining productization).

`app/core/template_version.py` resolves it at runtime and is the only reader. Nothing else
hard-codes a template version; the CLI, the manifest and `InstanceMetadata` all obtain it
from there. The Python distribution version in `pyproject.toml` is a separate concern
(packaging identity, not template identity) and is documented as such.

`CHANGELOG.md` records releases, opening with the productization entry.

### 2. Instance profile

A human-editable YAML file describes one client instance. YAML is chosen for comments and
readability; PyYAML is the single new runtime dependency, loaded with `safe_load`.

```
instance/client-profile.example.yaml   annotated template to copy
instance/demo-profile.yaml             the profile the demo store uses
```

The profile carries **identity and defaults only**: profile schema version, intended
template version, client slug, store name, domain metadata, locale, timezone, currency
code and symbol, contact defaults, theme colours, enabled features, homepage section
defaults, and static page metadata.

Validation is a Pydantic model (`app/instance/profile.py`) reusing the stack already in the
project. It rejects, with explicit messages:

- slugs that are not `^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$`
- unsupported `profile_schema_version`
- colours that are not `#RRGGBB`
- unknown feature flags (validated against a fixed set)
- unknown top-level keys (`extra="forbid"`), which is what makes the next rule work
- missing required values
- currency codes that are not three uppercase letters

**Secrets are rejected structurally, not by blocklist.** Because the model forbids extra
keys, any `database_url`, `secret_key`, `admin_password` or credential-shaped field fails
validation as an unknown key. A dedicated check additionally scans for secret-like key
names at every nesting depth so the error message says *why* rather than just "unknown
field". Secrets stay exclusively in environment variables.

### 3. Instance metadata

One new table, `instance_metadata`, single-row, with an Alembic revision `0002` on top of
`0001_initial`:

```
instance_slug           unique
template_version        version at initialization
profile_schema_version
profile_hash            sha256 of the canonical profile document
enabled_features        JSON list
initialized_at
last_bootstrap_at
```

No `tenant_id`, no per-row scoping anywhere else. The table answers "what is this instance
and where did it come from", nothing more. `profile_hash` makes profile drift visible
without storing the profile itself.

### 4. Instance CLI

`scripts/instance_cli.py`, argparse with four subcommands, matching the existing
`app.initial_data` / `scripts.seed` convention. No new CLI framework for four commands.
Exposed as `commerce-instance` in `[project.scripts]`.

| Command | Behaviour |
| --- | --- |
| `validate` | Parse and validate the profile. No database access at all. |
| `plan` | Open a read-only session, compute intended actions, print them as `create` / `skip` / `conflict`. Deterministic ordering. Rolls back; writes nothing. |
| `apply` | Requires `--profile` and a configured `DATABASE_URL`. Runs application-level initialization only. Idempotent. |
| `manifest` | Prints (or `--output`s) a non-secret JSON manifest. |

`plan` and `apply` share one planner so the plan is an honest preview: `apply` executes the
same computed action list rather than re-deriving it.

`apply` semantics:

- Initializes `StoreSettings` from the profile **only when the row does not exist**, or
  when a field is still at its shipped default. Any value the owner has edited through
  Admin is preserved — this is the property that makes re-running safe.
- Creates missing home sections and standard static pages; existing ones are skipped, never
  rewritten. This is the key difference from the demo seed, which deliberately overwrites.
- Records or updates `InstanceMetadata`, refreshing `last_bootstrap_at`.
- Creates **no** products, orders, coupons or admin accounts.
- Refuses to run when the stored `instance_slug` differs from the profile's, exiting
  non-zero with a `conflict` rather than silently rebranding a live store.

Admin creation stays the separate, explicit `app.initial_data` command.

### 5. Demo seed versus client bootstrap

Two clearly separated workflows, both idempotent:

- **Demo seed** (`scripts/seed.py`, unchanged behaviour) — rich sample catalogue, orders,
  coupons and content, for development and demonstration. It intentionally overwrites its
  own seeded content on each run.
- **Client bootstrap** (`commerce-instance apply`) — identity and structural defaults only,
  no commercial data, preserving owner edits.

The demo store is itself expressed as a profile (`instance/demo-profile.yaml`), so the two
paths share one identity format.

### 6. Feature configuration

A fixed set — `packages`, `silicone_molds`, `articles`, `coupons` — each already
implemented. The profile's `features` block seeds which optional home sections bootstrap
creates and is recorded in `InstanceMetadata`. Disabling a feature never deletes data; it
only affects what a *fresh* instance starts with. No dynamic plugin system, and no change
to API or Admin behaviour.

### 7. Offline MySQL compatibility check

`scripts/mysql_compat.py` (`commerce-mysql-check`) compiles the existing metadata against
SQLAlchemy's MySQL dialect **without connecting to anything**. It reports on: `CREATE
TABLE` and index compilation for every table, `Numeric` money columns, JSON columns,
indexed/unique `String` lengths against the InnoDB 3072-byte key limit under `utf8mb4`,
foreign keys, unique constraints, enum-like string columns, and the presence of an Alembic
head revision.

This is a portability *signal*. The documentation states plainly that an ephemeral MySQL
integration test is still required before a first deployment. No live MySQL CI service is
added.

### 8. Documentation

Updated in place rather than duplicated: `docs/local-setup.md` gains the two-workflow
distinction, and a new `docs/client-lifecycle.md` covers create / operate / upgrade /
backup-restore. A short "future instance factory" section documents the eventual
`validate → plan → apply` server-side provisioning phase — explicitly marked as unbuilt.
No script in this change touches server services, databases or Nginx.

## Risks

The main one is bootstrap accidentally overwriting owner content. Mitigated by
create-if-missing semantics, the "still at shipped default" rule for settings fields, and a
test that edits content through the model and asserts a second `apply` leaves it intact.
