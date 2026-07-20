# Event Naming Convention

## Rule

Use dotted lowercase names for transport topics and retain PascalCase event type in payload.

- Topic: `<domain>.<entity>.<action>` (example: `identity.user.created`)
- Payload field `event_type`: `UserCreated`

## Versioning

- Event schema id: `<EventType>.v<major>`.
- Breaking payload changes require major version bump.
