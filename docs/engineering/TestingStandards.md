# Testing Standards

## Coverage policy

- Unit tests for domain logic.
- Integration tests for cross-service and data interactions.
- Contract tests for external interfaces.

## Quality gates

- New behavior requires tests.
- Regressions require failing test first, then fix.
- CI must run deterministic tests without manual setup.
