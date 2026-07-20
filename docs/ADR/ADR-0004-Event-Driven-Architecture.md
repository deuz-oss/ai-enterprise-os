# ADR-0004 Event-Driven Architecture

- Status: Accepted
- Date: 2026-07-20
- Deciders: Platform Engineering

## Context

Synchronous-only service communication creates coupling and limits throughput.

## Decision

Adopt event-driven communication with NATS JetStream for asynchronous workflows.

## Consequences

- Better decoupling and resilience.
- Increased complexity for ordering, idempotency, and observability.
