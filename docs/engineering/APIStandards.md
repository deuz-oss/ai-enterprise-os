# API Standards

## Contract

- API surface is versioned (`/api/v1`).
- OpenAPI is the source of truth.
- Breaking changes require ADR and migration plan.

## HTTP conventions

- `GET` for read-only.
- `POST` for create/actions.
- `PUT` for full update.
- `PATCH` for partial update.
- `DELETE` for removal.

## Response shape

- Success responses are typed and documented.
- Error responses follow a common schema:
  - `code`
  - `message`
  - `details`
  - `correlation_id`
