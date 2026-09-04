from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import RECRUITMENT_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.audit.schemas import AuditLogOut
from app.modules.recruitment import service
from app.modules.recruitment.models import (
    CandidateStatus,
    JobOrderStatus,
    PlacementStatus,
)
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateExperienceCreate,
    CandidateExperienceOut,
    CandidateOut,
    CandidateUpdate,
    InterviewScheduleCreate,
    InterviewScheduleOut,
    InterviewScheduleUpdate,
    JobOrderCreate,
    JobOrderExtractOut,
    JobOrderGenerateDocumentIn,
    JobOrderOut,
    JobOrderTemplateCreate,
    JobOrderTemplateOut,
    JobOrderTemplateUpdate,
    JobOrderUpdate,
    MatchRequest,
    MatchResult,
    OfferingSendIn,
    OfferingSummaryOut,
    PlacementCreate,
    PlacementOut,
    PlacementUpdate,
    ReferralProgramSettingIn,
    ReferralProgramSettingOut,
    ReferralRewardOut,
)

router = APIRouter(
    prefix="/recruitment",
    tags=["recruitment"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*RECRUITMENT_ROLES))],
)

# ---------- Job orders ----------


@router.get("/job-orders", response_model=list[JobOrderOut])
def list_job_orders(
    response: Response,
    client_id: str | None = None,
    jo_status: JobOrderStatus | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.list_job_orders(
        db, client_id=client_id, status=jo_status, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


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


# ---------- Template & generate dokumen Job Order (Fase 21 item 4) ----------


@router.get("/job-order-templates", response_model=list[JobOrderTemplateOut])
def list_job_order_templates(active_only: bool = False, db: Session = Depends(get_db)):
    return service.list_job_order_templates(db, active_only=active_only)


@router.post(
    "/job-order-templates", response_model=JobOrderTemplateOut, status_code=status.HTTP_201_CREATED
)
def create_job_order_template(payload: JobOrderTemplateCreate, db: Session = Depends(get_db)):
    return service.create_job_order_template(db, payload)


@router.get("/job-order-templates/{template_id}", response_model=JobOrderTemplateOut)
def get_job_order_template(template_id: str, db: Session = Depends(get_db)):
    return service.get_job_order_template(db, template_id)


@router.patch("/job-order-templates/{template_id}", response_model=JobOrderTemplateOut)
def update_job_order_template(
    template_id: str, payload: JobOrderTemplateUpdate, db: Session = Depends(get_db)
):
    return service.update_job_order_template(db, template_id, payload)


@router.post("/job-orders/{jo_id}/generate-document", response_model=JobOrderOut)
def generate_job_order_document(
    jo_id: str, payload: JobOrderGenerateDocumentIn, db: Session = Depends(get_db)
):
    return service.generate_job_order_document(db, jo_id, str(payload.template_id))


@router.get("/job-orders/{jo_id}/generated-document/download-url")
def job_order_generated_document_download_url(jo_id: str, db: Session = Depends(get_db)):
    return {"url": service.job_order_generated_document_download_url(db, jo_id)}


# ---------- Candidates ----------


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(
    response: Response,
    candidate_status: CandidateStatus | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.list_candidates(
        db, status=candidate_status, q=q, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


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


@router.get("/candidates/{candidate_id}/activity-log", response_model=list[AuditLogOut])
def candidate_activity_log(
    candidate_id: str, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
):
    """Fase 24 -- Log Book kandidat."""
    return service.candidate_activity_log(db, candidate_id, limit=limit)


@router.post(
    "/candidates/{candidate_id}/experiences",
    response_model=CandidateExperienceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate_experience(
    candidate_id: str, payload: CandidateExperienceCreate, db: Session = Depends(get_db)
):
    return service.create_candidate_experience(db, candidate_id, payload)


@router.get("/candidates/{candidate_id}/experiences", response_model=list[CandidateExperienceOut])
def list_candidate_experiences(candidate_id: str, db: Session = Depends(get_db)):
    return service.list_candidate_experiences(db, candidate_id)


@router.delete("/candidates/experiences/{experience_id}", status_code=204)
def delete_candidate_experience(experience_id: str, db: Session = Depends(get_db)):
    service.delete_candidate_experience(db, experience_id)


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


@router.post("/placements/{placement_id}/offering-call", response_model=PlacementOut)
def record_offering_call(placement_id: str, db: Session = Depends(get_db)):
    """Fase 21 item 2 — catat offering call, independen dari offering letter."""
    return service.record_offering_call(db, placement_id)


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


# ---------- Program referral karyawan (Fase 27) ----------


@router.get("/referral-setting", response_model=ReferralProgramSettingOut)
def get_referral_setting(db: Session = Depends(get_db)):
    return service.get_referral_setting(db)


@router.put("/referral-setting", response_model=ReferralProgramSettingOut)
def update_referral_setting(payload: ReferralProgramSettingIn, db: Session = Depends(get_db)):
    return service.update_referral_setting(db, payload.is_enabled, payload.reward_amount)


@router.get("/referral-rewards", response_model=list[ReferralRewardOut])
def list_referral_rewards(employee_id: str | None = Query(None), db: Session = Depends(get_db)):
    return service.list_referral_rewards(db, employee_id=employee_id)


@router.post("/referral-rewards/{reward_id}/mark-paid", response_model=ReferralRewardOut)
def mark_referral_reward_paid(reward_id: str, db: Session = Depends(get_db)):
    return service.mark_referral_reward_paid(db, reward_id)
