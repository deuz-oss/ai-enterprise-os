# identity-service

Foundation FastAPI service for identity domain APIs.

## Run locally

```bash
uv run uvicorn identity_service.main:app --app-dir src --reload --port 8000
```

## Health endpoint

- `GET /healthz`
