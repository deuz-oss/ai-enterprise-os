# Logging Standards

## Format

- Structured JSON logs in all runtime environments.
- Include: `timestamp`, `level`, `service`, `message`, `correlation_id`.

## Levels

- `DEBUG`: local troubleshooting only.
- `INFO`: normal business/technical lifecycle events.
- `WARN`: recoverable anomalies.
- `ERROR`: failures requiring intervention.
