# AGENTS.md

Guidance for AI coding agents working in this repo.

## Stack

- **Backend** (`backend/`): FastAPI modular monolith, Python 3.12+, SQLAlchemy 2, Alembic. Install with `pip install -e ".[dev]"` into `backend/.venv`.
- **Frontend** (`frontend/`): React 18 + TypeScript + Vite + Tailwind + TanStack Query. No frontend test runner or ESLint is configured.
- Tooling config lives in **two** places: root `pyproject.toml` (ruff/mypy/pytest) and `backend/pyproject.toml` (deps, pytest). Ruff line-length is 100.

## Commands

Run backend commands from `backend/` (this is what the Makefile wraps):

```bash
make lint        # ruff check app tests  +  mypy app  (from repo root)
make test        # cd backend && pytest -q
make fmt         # ruff format + ruff check --fix
```

- Single test: `cd backend && python -m pytest tests/test_presales.py::test_name -q`
- Frontend verification (also the TS typecheck): `cd frontend && npm run build` (runs `tsc && vite build`)
- Tests don't need Docker/DB services: `conftest.py` swaps in in-memory SQLite via `dependency_overrides[get_db]` and sets `APP_ENV=test`.
- CI (`.github/workflows/ci.yml`) runs ruff on `backend`, mypy on `backend/app`, pytest from repo root, frontend build, and Docker builds — mirror these locally before pushing.
- Test auth helper `_auth_header` seeds an admin **directly via DB**, then logs in: `/auth/register` is admin-only by design.

## Config & environment quirks

- Settings come from `backend/app/core/config.py` (pydantic-settings). It loads **both** `backend/.env` and the repo-root `.env`. Copy `.env.example` to repo-root `.env`.
- Empty env vars are treated as **unset** (`_empty_to_none` validator): leaving `DATABASE_URL=` blank selects local mode — SQLite at `data/aeos.db`, uploads at `data/uploads/` (all gitignored).
- On startup (non-test), the app runs `Base.metadata.create_all`, ensures storage, and creates the admin user from `ADMIN_EMAIL`/`ADMIN_PASSWORD`. There are **no Alembic migrations yet** (`alembic/versions/` is empty); local dev relies on `create_all`.
- `APP_ENV != "test"` gates startup side effects — keep this behavior when touching `main.py`.

## Adding a domain module

Follow the existing pattern exactly (template: `backend/app/modules/presales`):

1. Create `models.py` / `schemas.py` / `service.py` / `router.py`.
2. Register the router in `backend/app/main.py` under prefix `/api/v1`.
3. Import the models module in `backend/alembic/env.py` (needed for future autogenerate).
4. Add tests in `backend/tests/`.

Routers use module-level guards: `dependencies=[Depends(get_current_user), Depends(require_roles(...))]` — replicate role restrictions per domain.

## Frontend notes

- Dev proxy: Vite forwards `/api` → `127.0.0.1:8000`; API client (`frontend/src/api/client.ts`) defaults `VITE_API_URL` to relative `/api/v1`. Only set `VITE_API_URL` for Docker builds.
- JWT lives in localStorage key `aeos_token`; 401 clears it.

## Conventions

- Docs, comments, and commit-facing prose are written in **Indonesian** (Bahasa Indonesia); code identifiers stay English. Match this.
- Pre-commit runs ruff/ruff-format only on `backend/` paths.
