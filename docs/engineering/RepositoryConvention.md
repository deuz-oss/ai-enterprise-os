# Repository Convention

## Structure ownership

- `apps/`: user-facing products
- `services/`: domain and platform services
- `packages/`: shared reusable libraries
- `tools/`: developer platform tooling
- `infra/`: local and platform runtime infrastructure

## Rules

- Keep shared logic in packages, not duplicated across services.
- Keep service boundaries explicit and dependency-light.
