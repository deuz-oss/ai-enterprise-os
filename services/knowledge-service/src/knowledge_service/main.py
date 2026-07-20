from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="knowledge-service", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service="knowledge-service")

