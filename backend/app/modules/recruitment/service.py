from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import parse_uuid
from app.modules import audit
from app.modules.clients.models import Client
from app.modules.recruitment.models import (
    Candidate,
    CandidateStatus,
    JobOrder,
    JobOrderStatus,
    Placement,
    PlacementStatus,
)
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateUpdate,
    JobOrderCreate,
    JobOrderUpdate,
    PlacementCreate,
)

# ---------- Job orders ----------


def _get_job_order(db: Session, jo_id: str) -> JobOrder:
    jo = db.get(JobOrder, parse_uuid(jo_id))
    if jo is None:
        raise HTTPException(status_code=404, detail="Job order tidak ditemukan")
    return jo


def create_job_order(db: Session, payload: JobOrderCreate) -> JobOrder:
    if db.get(Client, parse_uuid(payload.client_id)) is None:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    jo = JobOrder(**payload.model_dump())
    db.add(jo)
    db.commit()
    db.refresh(jo)
    # Fase 11: channel otomatis per job order (#jo-…)
    try:
        from app.modules.chat.service import ensure_job_order_channel

        ensure_job_order_channel(db, jo)
    except Exception:
        pass
    return jo


def list_job_orders(
    db: Session, client_id: str | None = None, status: JobOrderStatus | None = None
) -> list[JobOrder]:
    stmt = select(JobOrder).order_by(JobOrder.created_at.desc())
    if client_id:
        stmt = stmt.where(JobOrder.client_id == parse_uuid(client_id))
    if status is not None:
        stmt = stmt.where(JobOrder.status == status)
    return list(db.execute(stmt).scalars())


def get_job_order(db: Session, jo_id: str) -> JobOrder:
    return _get_job_order(db, jo_id)


def update_job_order(db: Session, jo_id: str, payload: JobOrderUpdate) -> JobOrder:
    jo = _get_job_order(db, jo_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(jo, field, value)
    db.commit()
    db.refresh(jo)
    return jo


def delete_job_order(db: Session, jo_id: str) -> None:
    jo = _get_job_order(db, jo_id)
    db.delete(jo)
    db.commit()


# ---------- Candidates ----------


def _get_candidate(db: Session, candidate_id: str) -> Candidate:
    candidate = db.get(Candidate, parse_uuid(candidate_id))
    if candidate is None:
        raise HTTPException(status_code=404, detail="Kandidat tidak ditemukan")
    return candidate


def create_candidate(db: Session, payload: CandidateCreate) -> Candidate:
    candidate = Candidate(**payload.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


async def upload_cv(db: Session, candidate_id: str, file: UploadFile) -> Candidate:
    candidate = _get_candidate(db, candidate_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File CV kosong")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran CV maksimal 25 MB")
    file_name = file.filename or "cv.pdf"
    candidate.cv_object_key = storage.new_object_key(f"candidates/{candidate.id}", file_name)
    content_type = file.content_type or "application/octet-stream"
    storage.put_object(candidate.cv_object_key, data, content_type)
    candidate.cv_file_name = file_name
    db.commit()
    db.refresh(candidate)
    audit.log_event(
        db,
        action="cv.upload",
        entity_type="candidate",
        entity_id=candidate.id,
        object_key=candidate.cv_object_key,
        detail={"file_name": file_name},
    )
    return candidate


def list_candidates(
    db: Session, status: CandidateStatus | None = None, q: str | None = None
) -> list[Candidate]:
    stmt = select(Candidate).order_by(Candidate.created_at.desc())
    if status is not None:
        stmt = stmt.where(Candidate.status == status)
    if q:
        stmt = stmt.where(Candidate.full_name.ilike(f"%{q}%"))
    return list(db.execute(stmt).scalars())


def get_candidate(db: Session, candidate_id: str) -> Candidate:
    return _get_candidate(db, candidate_id)


def update_candidate(db: Session, candidate_id: str, payload: CandidateUpdate) -> Candidate:
    candidate = _get_candidate(db, candidate_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)
    db.commit()
    db.refresh(candidate)
    return candidate


def delete_candidate(db: Session, candidate_id: str) -> None:
    candidate = _get_candidate(db, candidate_id)
    db.delete(candidate)
    db.commit()


def cv_download_url(db: Session, candidate_id: str) -> str:
    candidate = _get_candidate(db, candidate_id)
    if not candidate.cv_object_key:
        raise HTTPException(status_code=404, detail="Kandidat belum punya CV")
    audit.log_event(
        db,
        action="cv.download_url",
        entity_type="candidate",
        entity_id=candidate.id,
        object_key=candidate.cv_object_key,
        detail={"file_name": candidate.cv_file_name},
    )
    return storage.presigned_get_url(candidate.cv_object_key)


# ---------- Placements ----------


def create_placement(db: Session, payload: PlacementCreate) -> Placement:
    candidate = _get_candidate(db, str(payload.candidate_id))
    jo = _get_job_order(db, str(payload.job_order_id))
    duplicate = db.execute(
        select(Placement).where(
            Placement.candidate_id == candidate.id,
            Placement.job_order_id == jo.id,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Kandidat sudah diusulkan ke job order ini")
    placement = Placement(**payload.model_dump())
    db.add(placement)
    candidate.status = CandidateStatus.interview
    if jo.status == JobOrderStatus.open:
        jo.status = JobOrderStatus.screening
    db.commit()
    db.refresh(placement)
    # Fase 11: channel proyek otomatis + invite outsourcing
    try:
        from app.modules.chat.service import ensure_project_channel

        ensure_project_channel(db, placement)
    except Exception:
        pass
    return placement


def list_placements(
    db: Session, job_order_id: str | None = None, status: PlacementStatus | None = None
) -> list[Placement]:
    stmt = select(Placement).order_by(Placement.created_at.desc())
    if job_order_id:
        stmt = stmt.where(Placement.job_order_id == parse_uuid(job_order_id))
    if status is not None:
        stmt = stmt.where(Placement.status == status)
    return list(db.execute(stmt).scalars())


def update_placement_status(
    db: Session, placement_id: str, new_status: PlacementStatus
) -> Placement:
    placement = db.get(Placement, parse_uuid(placement_id))
    if placement is None:
        raise HTTPException(status_code=404, detail="Placement tidak ditemukan")
    placement.status = new_status
    candidate = db.get(Candidate, placement.candidate_id)
    jo = db.get(JobOrder, placement.job_order_id)
    if candidate and jo:
        if new_status == PlacementStatus.onboarded:
            candidate.status = CandidateStatus.placed
            active = db.execute(
                select(Placement).where(
                    Placement.job_order_id == jo.id,
                    Placement.status == PlacementStatus.onboarded,
                )
            ).scalars()
            if len(list(active)) >= jo.headcount:
                jo.status = JobOrderStatus.filled
        elif new_status == PlacementStatus.cancelled and candidate.status in (
            CandidateStatus.interview,
            CandidateStatus.offered,
        ):
            candidate.status = CandidateStatus.rejected
    db.commit()
    db.refresh(placement)
    return placement
