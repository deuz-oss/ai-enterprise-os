from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import PRESALES_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.clients.schemas import ClientOut
from app.modules.presales import service
from app.modules.presales.models import LeadStage
from app.modules.presales.schemas import (
    ActivityCreate,
    ActivityOut,
    FunnelStats,
    LeadCreate,
    LeadOut,
    LeadUpdate,
)

router = APIRouter(
    prefix="/leads",
    tags=["presales"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)


@router.get("", response_model=list[LeadOut])
def list_leads(
    response: Response,
    stage: LeadStage | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.list_leads(db, stage=stage, q=q, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/funnel", response_model=FunnelStats)
def funnel(db: Session = Depends(get_db)):
    return service.funnel_stats(db)


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    return service.create_lead(db, payload)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    return service.get_lead(db, lead_id)


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: str, payload: LeadUpdate, db: Session = Depends(get_db)):
    return service.update_lead(db, lead_id, payload)


@router.delete("/{lead_id}", status_code=204)
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    service.delete_lead(db, lead_id)


@router.post("/{lead_id}/convert", response_model=ClientOut, status_code=201)
def convert_lead(lead_id: str, db: Session = Depends(get_db)):
    """Konversi lead menjadi klien (untuk lead yang sudah deal)."""
    return service.convert_lead_to_client(db, lead_id)


@router.post("/{lead_id}/activities", response_model=ActivityOut, status_code=201)
def add_activity(lead_id: str, payload: ActivityCreate, db: Session = Depends(get_db)):
    return service.add_activity(db, lead_id, payload.activity_type, payload.content)


@router.get("/{lead_id}/activities", response_model=list[ActivityOut])
def list_activities(lead_id: str, db: Session = Depends(get_db)):
    lead = service.get_lead(db, lead_id)
    return list(lead.activities)
