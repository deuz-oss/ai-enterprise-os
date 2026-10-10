from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import (
    AI_FINANCE_ROLES,
    AI_HR_ROLES,
    AI_PRESALES_ROLES,
    AI_RECRUITMENT_ROLES,
)
from app.core.security import get_current_user, require_roles, require_tenant_user
from app.modules.ai import forecast as forecast_service
from app.modules.ai import rag as rag_service
from app.modules.ai import service as ai_service
from app.modules.ai.schemas import (
    AskRequest,
    AskResultOut,
    ContractIndexOut,
    ForecastOut,
    ForecastRequest,
    IndexedContractOut,
    LeadBriefOut,
    MatchResultOut,
    ScreeningOut,
    ScreeningRequest,
)

# Fitur AI direkrutmen → akses selaras dengan modul recruitment.
recruitment_router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*AI_RECRUITMENT_ROLES))],
)


@recruitment_router.post("/candidates/{candidate_id}/screen", response_model=ScreeningOut)
def screen_candidate(
    candidate_id: UUID,
    payload: ScreeningRequest | None = None,
    db: Session = Depends(get_db),
):
    job_order_id = payload.job_order_id if payload else None
    return ai_service.screen_candidate(db, candidate_id, job_order_id)


@recruitment_router.get("/candidates/{candidate_id}/screenings", response_model=list[ScreeningOut])
def list_screenings(candidate_id: UUID, db: Session = Depends(get_db)):
    return ai_service.list_screenings(db, candidate_id)


@recruitment_router.post("/job-orders/{job_order_id}/match", response_model=MatchResultOut)
def match_job_order(job_order_id: UUID, db: Session = Depends(get_db)):
    result = ai_service.match_job_order(db, job_order_id)
    if result.evaluated == 0:
        raise HTTPException(
            status_code=422,
            detail="Tidak ada kandidat aktif untuk dicocokkan (status baru/screening/interview)",
        )
    return result


# Q&A kontrak kerja → domain HR.
hr_router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*AI_HR_ROLES))],
)


@hr_router.get("/contracts/indexed", response_model=list[IndexedContractOut])
def list_indexed_contracts(db: Session = Depends(get_db)):
    return rag_service.list_indexed(db)


@hr_router.post("/contracts/ask", response_model=AskResultOut)
def ask_contracts(payload: AskRequest, db: Session = Depends(get_db)):
    return rag_service.ask(db, payload.question, payload.employee_id)


@hr_router.post("/contracts/{contract_id}/index", response_model=ContractIndexOut)
def index_contract(contract_id: UUID, db: Session = Depends(get_db)):
    return rag_service.index_contract(db, contract_id)


# Forecast arus kas → domain finance.
finance_router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*AI_FINANCE_ROLES))],
)


@finance_router.post("/finance/forecast", response_model=ForecastOut)
def cash_flow_forecast(payload: ForecastRequest | None = None, db: Session = Depends(get_db)):
    months_ahead = payload.months_ahead if payload else 3
    return forecast_service.forecast_cash_flow(db, months_ahead)


# Fase 48 -- ringkasan AI lead → domain presales.
presales_router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*AI_PRESALES_ROLES))],
)


@presales_router.post("/leads/{lead_id}/brief", response_model=LeadBriefOut)
def generate_lead_brief(lead_id: UUID, db: Session = Depends(get_db)):
    return ai_service.generate_lead_brief(db, lead_id)


@presales_router.get("/leads/{lead_id}/brief", response_model=LeadBriefOut | None)
def get_lead_brief(lead_id: UUID, db: Session = Depends(get_db)):
    return ai_service.get_latest_lead_brief(db, lead_id)


# Palet ⌘K: kalimat bebas -> daftar terfilter (peluang AI #5). Hanya navigasi --
# halaman tujuan menegakkan RBAC-nya sendiri; akun karyawan (ESS) tidak
# memakai palet admin.
def _staff_only(user=Depends(get_current_user)):
    if getattr(user.role, "value", user.role) == "karyawan":
        raise HTTPException(status_code=403, detail="Fitur ini untuk staf perusahaan")
    return user


nav_router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user()), Depends(_staff_only)],
)


@nav_router.post("/nav-query")
def palette_nav_query(payload: dict, db: Session = Depends(get_db)):
    """Terjemahkan kalimat ke URL daftar terfilter; tidak mengubah data apa pun."""
    from app.modules.ai.nav_query import nav_query

    return nav_query(db, str((payload or {}).get("text") or ""))
