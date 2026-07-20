# ADR-0002 Service Boundaries

- Status: Accepted
- Date: 2026-07-20
- Deciders: Platform Engineering

## Context

Future scale requires independent deployment, ownership, and release cadence per domain.

## Decision

Define one service per business/platform capability with explicit APIs and event contracts.

## Consequences

- Better autonomy and scale.
- Requires stronger contract governance and observability.
