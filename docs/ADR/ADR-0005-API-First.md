# ADR-0005 API First

- Status: Accepted
- Date: 2026-07-20
- Deciders: Platform Engineering

## Context

Implementation-first APIs cause contract drift and integration failures.

## Decision

All services must define and publish OpenAPI contracts first, then implement handlers.

## Consequences

- More predictable integrations and testing.
- Requires automated spec generation and validation in CI.
