# Development

## Requirements

- Docker + Docker Compose
- Python 3.13+
- Node.js 20+
- Flutter 3.24+

## Local setup

1. Copy `.env.example` to `.env`.
2. Start infrastructure and platform services with `make dev`.
3. Start web apps with:
   - `cd apps/web-admin && npm install && npm run dev`
   - `cd apps/web-portal && npm install && npm run dev`
4. Run tests with `make test`.

## Service development

Each service is isolated under `services/<service-name>` and includes:

- `pyproject.toml`
- `Dockerfile`
- `src/<service_package>/main.py`
- `tests/test_health.py`

## Code quality

- Pre-commit enforces Ruff, Black, isort, mypy, ESLint, and Prettier.
- CI runs lint, test, and docker build checks.
