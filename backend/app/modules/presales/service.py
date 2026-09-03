from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules.presales.models import ActivityType, Lead, LeadActivity, LeadStage
from app.modules.presales.schemas import (
    FunnelStage,
    FunnelStats,
    LeadCreate,
    LeadUpdate,
)


def _get(db: Session, lead_id: str) -> Lead:
    lead = db.get(Lead, parse_uuid(lead_id))
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead tidak ditemukan")
    return lead


def create_lead(db: Session, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def list_leads(
    db: Session,
    stage: LeadStage | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    """`limit` default 200, pola sama seperti `recruitment.list_candidates`
    (Batch 1c)."""
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if stage is not None:
        stmt = stmt.where(Lead.stage == stage)
    if q:
        stmt = stmt.where(Lead.company_name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


def get_lead(db: Session, lead_id: str) -> Lead:
    return _get(db, lead_id)


def update_lead(db: Session, lead_id: str, payload: LeadUpdate) -> Lead:
    lead = _get(db, lead_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead_id: str) -> None:
    lead = _get(db, lead_id)
    db.delete(lead)
    db.commit()


def add_activity(
    db: Session, lead_id: str, activity_type: ActivityType, content: str
) -> LeadActivity:
    lead = _get(db, lead_id)
    activity = LeadActivity(lead_id=lead.id, activity_type=activity_type, content=content)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def funnel_stats(db: Session) -> FunnelStats:
    rows = db.execute(
        select(
            Lead.stage,
            func.count(Lead.id),
            func.coalesce(func.sum(Lead.estimated_value), 0.0),
        ).group_by(Lead.stage)
    ).all()
    counts = {s: int(c) for s, c, _ in rows}
    values = {s: float(v or 0.0) for s, _, v in rows}
    stages = [
        FunnelStage(stage=s, count=counts.get(s, 0), total_estimated_value=values.get(s, 0.0))
        for s in LeadStage
    ]
    return FunnelStats(
        stages=stages,
        total_leads=sum(counts.values()),
        won_leads=counts.get(LeadStage.won, 0),
        lost_leads=counts.get(LeadStage.lost, 0),
    )


def convert_lead_to_client(db: Session, lead_id: str):
    """Mengubah lead menjadi klien (dipakai saat lead mencapai tahap deal).

    Data PIC dan nama perusahaan disalin ke master klien; lead ditandai `deal`
    dan terhubung ke klien hasil konversi. Konversi ganda ditolak.
    """
    from app.modules.clients.models import Client

    lead = _get(db, lead_id)
    existing = db.execute(select(Client).where(Client.lead_id == lead.id)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Lead ini sudah dikonversi menjadi klien")

    client = Client(
        name=lead.company_name,
        pic_name=lead.contact_name,
        pic_phone=lead.contact_phone,
        pic_email=lead.contact_email,
        lead_id=lead.id,
    )
    lead.stage = LeadStage.won
    db.add(client)
    db.commit()
    db.refresh(client)
    return client
