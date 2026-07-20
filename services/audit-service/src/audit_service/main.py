from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="audit-service", version="0.1.0")


class StatusResponse(BaseModel):
    status: str
    service: str


@app.get("/health/live", response_model=StatusResponse)
def health_live() -> StatusResponse:
    return StatusResponse(status="ok", service="audit-service")


@app.get("/health/ready", response_model=StatusResponse)
def health_ready() -> StatusResponse:
    return StatusResponse(status="ok", service="audit-service")


@app.get("/version")
def version() -> dict[str, str]:
    return {"service": "audit-service", "version": "0.1.0"}


@app.get("/metrics")
def metrics() -> dict[str, object]:
    return {"service": "audit-service", "requests_total": 0, "errors_total": 0}
