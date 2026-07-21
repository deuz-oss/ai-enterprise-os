# Service Convention

Each service must include:

- `Dockerfile`
- `README.md`
- `pyproject.toml`
- `src/<service_name>/`
- `tests/`

## Required runtime endpoints

- `/health/live`
- `/health/ready`
- `/version`
- `/metrics`
