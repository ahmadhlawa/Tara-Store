# Tara Store Fork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an independent, clean Tara Store project from Vista commit `0589a945ba454b9a53af519ce35b2e4f996a950c`.

**Architecture:** Export only committed source into a new repository, preserve reusable code and migrations, and bootstrap a clean Tara-local SQLite instance and media root through existing configuration. Do not transfer client data, runtime artifacts, secrets, or Git metadata.

**Tech Stack:** React/Vite, FastAPI, SQLAlchemy, Alembic, SQLite.

## Global Constraints

- Source: `D:\Project\vista-store-e-commerce` at `0589a945ba454b9a53af519ce35b2e4f996a950c`; do not modify it.
- Destination: `D:\Project\Tara-Store`; no remote or push.
- Exclude environments, databases, uploads, generated datasets, builds, logs, test artifacts, and secrets.
- Verify backend on port 8002 and frontend on port 5176.

### Task 1: Export source and initialize Tara Git

**Files:**
- Create: committed Vista source files in `D:\Project\Tara-Store`
- Create: `PROJECT_FORK_NOTES.md`

- [ ] Export `0589a945ba454b9a53af519ce35b2e4f996a950c` using `git archive`, which cannot include Git metadata or untracked runtime data.
- [ ] Initialize a new repository without a remote and retain the committed `.gitignore`.
- [ ] Record fork source, exclusions, identity, branding follow-ups, and verification evidence in `PROJECT_FORK_NOTES.md`.

### Task 2: Bootstrap clean Tara runtime

**Files:**
- Modify: Tara-local environment configuration only, if required by existing bootstrap scripts
- Create: ignored Tara SQLite database and empty media directory through the existing architecture

- [ ] Inspect only relevant existing environment, Alembic, and startup configuration.
- [ ] Configure the Tara-local SQLite identity without copying a source database or credentials.
- [ ] Run migrations to Alembic head and assert no client catalog, order, invoice, media, coupon, delivery-area, or administrator data exists.

### Task 3: Verify and commit

**Files:**
- Modify: `PROJECT_FORK_NOTES.md` with observed results

- [ ] Start only Tara backend/frontend processes on 8002/5176 and verify health, storefront, and admin login/return navigation.
- [ ] Run the frontend production build once.
- [ ] Confirm source remains clean and Tara staging excludes ignored runtime/secrets artifacts.
- [ ] Create exactly one initial commit: `chore: initialize Tara Store commerce project`.
