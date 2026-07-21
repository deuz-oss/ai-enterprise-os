# Developer Guide

## Quick start

1. Copy environment file: `.env.example` to `.env`.
2. Run `python tools/aeos/src/aeos/cli.py doctor`.
3. Start local stack with `make dev`.
4. Generate OpenAPI artifacts with `python tools/aeos/src/aeos/cli.py docs`.

## Generate components

- `python tools/aeos/src/aeos/cli.py new service <name>`
- `python tools/aeos/src/aeos/cli.py new package <name>`
- `python tools/aeos/src/aeos/cli.py new app <name>`
- `python tools/aeos/src/aeos/cli.py new agent <name>`

## Standards

- Engineering standards: `docs/engineering/INDEX.md`
- ADRs: `docs/adr/ADR-INDEX.md`
- Event schemas: `schemas/events/`
