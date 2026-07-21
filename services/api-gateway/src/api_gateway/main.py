from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="api-gateway", version="0.1.0")


class StatusResponse(BaseModel):
    status: str
    service: str


@app.get("/health/live", response_model=StatusResponse)
def health_live() -> StatusResponse:
    return StatusResponse(status="ok", service="api-gateway")


@app.get("/health/ready", response_model=StatusResponse)
def health_ready() -> StatusResponse:
    return StatusResponse(status="ok", service="api-gateway")


@app.get("/version")
def version() -> dict[str, str]:
    return {"service": "api-gateway", "version": "0.1.0"}


@app.get("/metrics")
def metrics() -> dict[str, object]:
    return {"service": "api-gateway", "requests_total": 0, "errors_total": 0}
