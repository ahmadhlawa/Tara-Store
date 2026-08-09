# Full-stack commerce MVP — implementation plan

Branch: `feat/fullstack-commerce-mvp`, based on `main` @ `2c418a4`.
`main` and `feat/frontend-foundation` are not touched. The frontend stays JavaScript/JSX.

## Phases and checkpoints

| # | Phase | Deliverable | Commit theme |
| --- | --- | --- | --- |
| 1 | Backend foundation | `pyproject.toml`, settings, engine/session, `/health`, app factory | `chore: establish FastAPI and local database foundation` |
| 2 | Models + migration | all 21 entities, Alembic env + initial revision | included in phase 1/3 commits |
| 3 | Auth | Argon2 hashing, JWT, `/auth/login`, `/auth/me`, role deps, admin CLI | `feat: add admin authentication and role authorization` |
| 4 | Catalog | products, images, specs, options, variants, package items, categories, public catalog reads | `feat: implement catalog and inventory management` |
| 5 | Content | store settings, hero slides, banners, home sections, articles, static pages | `feat: implement store content and settings management` |
| 6 | Commerce | coupons, delivery areas, pricing service, guest checkout, orders, status history, audit log | `feat: implement guest checkout and order management` |
| 7 | Media | storage interface, local provider, R2 adapter boundary, upload endpoint, media assets | `feat: add local media storage` |
| 8 | Storefront | API client, services, React Router, all public routes | `feat: connect storefront to commerce API` |
| 9 | Admin app | login, layout, all admin workspaces | `feat: add commerce admin workspace` |
| 10 | Tests + seed | backend pytest suite, Vitest suite, idempotent seed | `test: cover commerce workflows` |
| 11 | Docs + deployment templates | README, docs set, inactive systemd/Nginx templates | `docs: document local full-stack commerce template` |

## Ordering constraints

- Models must exist before the Alembic revision is generated.
- The pricing service must exist before order endpoints.
- The public API must be stable before the storefront is rewired.
- Seed data depends on every model and on the media helper.

## Verification gate (run at the end, not per file)

Backend: clean-database `alembic upgrade head`, `seed`, `pytest` with coverage,
app import + `/health` + OpenAPI generation.
Frontend: `npm ci`, `vitest run`, `vite build`.
Repository: `git diff --check`, no tracked `node_modules`/`dist`/`*.db`/uploads/`.env`,
`main` unchanged, branch pushed.

## Explicitly out of scope for this task

Deploying anything, touching MySQL/Redis/Nginx/systemd/SSH/production, merging
branches, converting the frontend to TypeScript, reusing `feat/frontend-foundation`.
