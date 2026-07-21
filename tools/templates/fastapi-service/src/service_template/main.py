from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="__NAME__", version="0.1.0")


class StatusResponse(BaseModel):
    status: str
    service: str


@app.get("/health/live", response_model=StatusResponse)
def health_live() -> StatusResponse:
    return StatusResponse(status="ok", service="__NAME__")


@app.get("/health/ready", response_model=StatusResponse)
def health_ready() -> StatusResponse:
    return StatusResponse(status="ok", service="__NAME__")


@app.get("/version")
def version() -> dict[str, str]:
    return {"service": "__NAME__", "version": "0.1.0"}


@app.get("/metrics")
def metrics() -> dict[str, object]:
    return {"service": "__NAME__", "requests_total": 0, "errors_total": 0}
