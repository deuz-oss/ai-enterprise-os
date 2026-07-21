# Coding Standards

## General

- Favor readability over cleverness.
- Keep functions small and single-purpose.
- Use explicit typing in Python and TypeScript.
- Fail fast with actionable error messages.

## Python

- Python 3.13+.
- Ruff + Black + isort + mypy are required.
- Pydantic v2 models for validated IO boundaries.

## TypeScript

- Strict mode required.
- No `any` unless justified in code review.
- Shared contracts belong in `packages/typescript-common/types`.
