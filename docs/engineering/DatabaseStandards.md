# Database Standards

## Baseline

- PostgreSQL is the primary relational store.
- SQLAlchemy 2.x + Alembic for schema lifecycle.
- All schema changes are migration-driven.

## Data rules

- Use UUID primary keys unless sequence-based IDs are explicitly required.
- Store timestamps in UTC.
- Soft delete rules must be explicit per aggregate.
- Every table must define ownership and retention metadata.
