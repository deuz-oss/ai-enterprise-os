from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import RECRUITMENT_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.recruitment import service
from app.modules.recruitment.models import (
    CandidateStatus,
    JobOrderStatus,
    PlacementStatus,
)
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateOut,
    CandidateUpdate,
    InterviewScheduleCreate,
    InterviewScheduleOut,
    InterviewScheduleUpdate,
    JobOrderCreate,
    JobOrderExtractOut,
    JobOrderOut,
    JobOrderUpdate,
    MatchRequest,
    MatchResult,
    OfferingSendIn,
    OfferingSummaryOut,
    PlacementCreate,
    PlacementOut,
    PlacementUpdate,
)

router = APIRouter(
    prefix="/recruitment",
    tags=["recruitment"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*RECRUITMENT_ROLES))],
)

# ---------- Job orders ----------


@router.get("/job-orders", response_model=list[JobOrderOut])
def list_job_orders(
    client_id: str | None = None,
    jo_status: JobOrderStatus | None = None,
    db: Session = Depends(get_db),
):
    return service.list_job_orders(db, client_id=client_id, status=jo_status)


@router.post("/job-orders", response_model=JobOrderOut, status_code=status.HTTP_201_CREATED)
def create_job_order(payload: JobOrderCreate, db: Session = Depends(get_db)):
    return service.create_job_order(db, payload)


@router.get("/job-orders/stale", response_model=list[JobOrderOut])
def list_stale_job_orders(db: Session = Depends(get_db)):
    """JO yang belum filled dan sudah >=30 hari sejak request_date (PRD v3.1 Patch 3)."""
    return service.list_stale_job_orders(db)


@router.post("/job-orders/extract", response_model=JobOrderExtractOut)
async def extract_job_order_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload dokumen Job Order/Manpower Requisition -> saran field via AI
    (PRD v3.1 Patch 3b). Belum membuat JobOrder — hasilnya dipakai pre-fill
    form create, object_key ikut dikirim balik ke POST /job-orders."""
    return await service.extract_job_order_document(db, file)


@router.get("/job-orders/{jo_id}/document/download-url")
def job_order_document_download_url(jo_id: str, db: Session = Depends(get_db)):
    return {"url": service.job_order_document_download_url(db, jo_id)}


@router.get("/job-orders/{jo_id}", response_model=JobOrderOut)
def get_job_order(jo_id: str, db: Session = Depends(get_db)):
    return service.get_job_order(db, jo_id)


@router.patch("/job-orders/{jo_id}", response_model=JobOrderOut)
def update_job_order(jo_id: str, payload: JobOrderUpdate, db: Session = Depends(get_db)):
    return service.update_job_order(db, jo_id, payload)


@router.delete("/job-orders/{jo_id}", status_code=204)
def delete_job_order(jo_id: str, db: Session = Depends(get_db)):
    service.delete_job_order(db, jo_id)


# ---------- Candidates ----------


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(
    candidate_status: CandidateStatus | None = None,
    q: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    return service.list_candidates(db, status=candidate_status, q=q)


@router.post("/candidates", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(payload: CandidateCreate, db: Session = Depends(get_db)):
    return service.create_candidate(db, payload)


@router.post("/candidates/{candidate_id}/cv", response_model=CandidateOut)
async def upload_cv(candidate_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await service.upload_cv(db, candidate_id, file)


@router.get("/candidates/{candidate_id}/cv-download-url")
def cv_download_url(candidate_id: str, db: Session = Depends(get_db)):
    return {"url": service.cv_download_url(db, candidate_id)}


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    return service.get_candidate(db, candidate_id)


@router.patch("/candidates/{candidate_id}", response_model=CandidateOut)
def update_candidate(candidate_id: str, payload: CandidateUpdate, db: Session = Depends(get_db)):
    return service.update_candidate(db, candidate_id, payload)


@router.delete("/candidates/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: str, db: Session = Depends(get_db)):
    service.delete_candidate(db, candidate_id)


# ---------- Placements ----------


@router.get("/placements", response_model=list[PlacementOut])
def list_placements(
    job_order_id: str | None = None,
    placement_status: PlacementStatus | None = None,
    db: Session = Depends(get_db),
):
    return service.list_placements(db, job_order_id=job_order_id, status=placement_status)


@router.post("/placements", response_model=PlacementOut, status_code=status.HTTP_201_CREATED)
def create_placement(payload: PlacementCreate, db: Session = Depends(get_db)):
    return service.create_placement(db, payload)


@router.get("/placements/offering-summary", response_model=OfferingSummaryOut)
def get_offering_summary(db: Session = Depends(get_db)):
    """Ringkasan pipeline offering — widget "Offering" Talent Cloud."""
    return service.offering_summary(db)


@router.patch("/placements/{placement_id}", response_model=PlacementOut)
def update_placement(placement_id: str, payload: PlacementUpdate, db: Session = Depends(get_db)):
    return service.update_placement_status(
        db,
        placement_id,
        payload.status,
        ojt_start_date=payload.ojt_start_date,
        ojt_end_date=payload.ojt_end_date,
    )


@router.post("/placements/{placement_id}/offering")
def send_offering(placement_id: str, payload: OfferingSendIn, db: Session = Depends(get_db)):
    """PRD v3.0 §4 aksi 2/3 "Offering": surat penawaran PDF branded -> esign."""
    from app.modules.esign.schemas import EsignRequestOut

    request = service.send_offering_letter(db, placement_id, payload)
    return EsignRequestOut.model_validate(request)


# ---------- Interviews — PRD v3.0 Talent Cloud ----------


@router.get("/interviews", response_model=list[InterviewScheduleOut])
def list_interviews(job_order_id: str | None = None, db: Session = Depends(get_db)):
    return service.list_interviews(db, job_order_id=job_order_id)


@router.post(
    "/interviews", response_model=InterviewScheduleOut, status_code=status.HTTP_201_CREATED
)
def create_interview(
    payload: InterviewScheduleCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return service.create_interview(db, payload, created_by=user.id)


@router.patch("/interviews/{interview_id}", response_model=InterviewScheduleOut)
def update_interview(
    interview_id: str, payload: InterviewScheduleUpdate, db: Session = Depends(get_db)
):
    return service.update_interview(db, interview_id, payload)


# ---------- AI Matching Native — PRD v3.0 Talent Cloud ----------


@router.post("/job-orders/{jo_id}/match", response_model=list[MatchResult])
def match_for_jo(jo_id: str, payload: MatchRequest | None = None, db: Session = Depends(get_db)):
    top_k = payload.top_k if payload else 50
    return service.match_candidates(db, jo_id, top_k=top_k, billable=True)


@router.get("/job-orders/{jo_id}/matches", response_model=list[MatchResult])
def get_matches(jo_id: str, top_k: int = 50, min_score: int = 0, db: Session = Depends(get_db)):
    results = service.match_candidates(db, jo_id, top_k=top_k)
    return [r for r in results if r["match_score"] >= min_score]
