# ADR-0001 Repository Structure

- Status: Accepted
- Date: 2026-07-20
- Deciders: Platform Engineering

## Context

The platform needs a long-lived monorepo with clear separation of concerns and scalable ownership.

## Decision

Adopt domain-oriented top-level folders (`apps`, `services`, `packages`, `infra`, `tools`, `docs`, `schemas`).

## Consequences

- Faster onboarding and navigation.
- Clear ownership boundaries.
- Requires governance to prevent cross-boundary coupling.
