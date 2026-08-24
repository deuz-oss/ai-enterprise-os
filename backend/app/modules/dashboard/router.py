from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_tenant_user
from app.modules.clients.models import Client, LegalDocument
from app.modules.presales.models import Lead, LeadStage
from app.modules.recruitment.models import Candidate, JobOrder, JobOrderStatus

# Agregat lintas modul — platform_admin diblokir agar tidak melihat data tenant.
router = APIRouter(
    prefix="/overview",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user())],
)


@router.get("")
def overview(db: Session = Depends(get_db)):
    lead_rows = db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)).all()
    leads = {stage.value: count for stage, count in lead_rows}

    open_job_orders = db.execute(
        select(func.count(JobOrder.id)).where(
            JobOrder.status.notin_([JobOrderStatus.filled, JobOrderStatus.closed])
        )
    ).scalar() or 0

    candidate_rows = db.execute(
        select(Candidate.status, func.count(Candidate.id)).group_by(Candidate.status)
    ).all()
    candidates = {status_.value: count for status_, count in candidate_rows}

    return {
        "leads": {
            "total": sum(leads.values()),
            "won": leads.get(LeadStage.won.value, 0),
            "by_stage": leads,
            "funnel": [
                {"stage": s.value, "count": leads.get(s.value, 0)}
                for s in LeadStage
            ],
        },
        "clients": db.execute(select(func.count(Client.id))).scalar() or 0,
        "documents": db.execute(select(func.count(LegalDocument.id))).scalar() or 0,
        "job_orders": {
            "open": int(open_job_orders),
            "filled": int(
                db.execute(
                    select(func.count(JobOrder.id)).where(JobOrder.status == JobOrderStatus.filled)
                ).scalar()
                or 0
            ),
        },
        "candidates": {"total": sum(candidates.values()), "by_status": candidates},
    }
