# Contributing

## Workflow

1. Create a feature branch from `main`.
2. Keep changes scoped to one concern.
3. Run `make lint` and `make test`.
4. Open a pull request with architecture impact notes.

## Engineering standards

- Follow repository standards and ASF specifications in `docs/`.
- Preserve domain boundaries across `apps/`, `services/`, `packages/`, and `infra/`.
- Keep APIs versioned and documented.
- Add tests for all behavior changes.

## Commit quality

- Use descriptive commit messages.
- Avoid unrelated file churn.
- Update documentation whenever structure or operations change.
