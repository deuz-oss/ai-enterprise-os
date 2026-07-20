# AI Enterprise OS

Production-grade monorepo foundation for a large-scale enterprise AI platform.

## Quick start

1. Copy environment file: `cp .env.example .env`
2. Start platform stack: `docker compose up -d --build`
3. Check services: `docker compose ps`

## Repository domains

- `apps/` frontend and mobile applications
- `services/` backend platform services (FastAPI)
- `agents/` autonomous AI agent runtimes
- `packages/` shared Python/TypeScript libraries
- `sdk/` external developer SDKs
- `infra/` local platform infrastructure configuration
- `tools/` internal developer tooling
- `scripts/` operational scripts
- `docs/` architecture and engineering standards

## Developer commands

- `make dev` start the full platform
- `make down` stop and remove runtime stack
- `make logs` stream compose logs
- `make lint` run Python and JS lint checks
- `make test` run test suites
- `make fmt` apply formatting
- `make migrate` run database migrations per service

## AEOS CLI

- Health check: `python tools/aeos/src/aeos/cli.py doctor`
- Initialize workspace: `python tools/aeos/src/aeos/cli.py init`
- Generate service: `python tools/aeos/src/aeos/cli.py new service <name>`
- Generate docs/openapi: `python tools/aeos/src/aeos/cli.py docs`
