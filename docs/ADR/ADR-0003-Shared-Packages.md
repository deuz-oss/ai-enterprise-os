# ADR-0003 Shared Packages

- Status: Accepted
- Date: 2026-07-20
- Deciders: Platform Engineering

## Context

Cross-cutting code duplication increases divergence and maintenance cost.

## Decision

Centralize common contracts and platform utilities in shared Python/TypeScript packages.

## Consequences

- Reduced duplication and consistent behavior.
- Requires semantic version discipline and compatibility testing.
