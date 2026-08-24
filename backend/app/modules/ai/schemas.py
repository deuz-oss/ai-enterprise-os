import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.ai.models import ScreeningVerdict
from app.modules.recruitment.schemas import CandidateOut


class ScreeningRequest(BaseModel):
    job_order_id: UUID | None = None


class ScreeningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    job_order_id: UUID | None
    score: int
    verdict: ScreeningVerdict
    summary: str
    strengths: list[str]
    risks: list[str]
    model: str
    created_at: datetime


class MatchItemOut(BaseModel):
    candidate: CandidateOut
    screening: ScreeningOut


class MatchResultOut(BaseModel):
    job_order_id: UUID
    evaluated: int
    reused: int
    results: list[MatchItemOut]


# ---- RAG Q&A kontrak ----


class ContractIndexOut(BaseModel):
    contract_id: UUID
    chunks: int


class IndexedContractOut(BaseModel):
    contract_id: UUID
    file_name: str | None
    employee_name: str
    chunks: int


class AskRequest(BaseModel):
    question: str
    employee_id: UUID | None = None


class AskSourceOut(BaseModel):
    contract_id: UUID
    employee_name: str | None
    contract_no: str | None
    score: float
    snippet: str


class AskResultOut(BaseModel):
    answer: str
    sources: list[AskSourceOut]


# ---- Forecast arus kas ----


class ForecastRequest(BaseModel):
    months_ahead: int = 3


class MonthlyFlow(BaseModel):
    year: int
    month: int
    inflow: float
    outflow: float
    net: float


class ForecastOut(BaseModel):
    history: list[MonthlyFlow]
    projection: list[MonthlyFlow]
    pending_receivables: float
    outlook: str
    summary: str
    risks: list[str]
    recommendations: list[str]
    model: str


def _load_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data] if isinstance(data, list) else []
