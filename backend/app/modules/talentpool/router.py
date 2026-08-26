"""Router Talent Pool & CV Standardization (Fase 13, PRD §10)."""

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.modules.talentpool import service
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/talentpool",
    tags=["talentpool"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("recruiter", "operations", "hr", "management")),
    ],
)


@router.get("")
def list_talentpool(
    q: str | None = Query(None),
    domisili: str | None = Query(None),
    skill: str | None = Query(None),
    readiness: str | None = Query(None),
    tp_status: str | None = Query(None),
    has_standard_cv: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    """Facet pencarian talent pool (PRD §10.5)."""
    return service.list_talentpool(
        db,
        q=q,
        domisili=domisili,
        skill=skill,
        readiness=readiness,
        tp_status=tp_status,
        has_standard_cv=has_standard_cv,
    )


@router.post("/intake", status_code=201)
async def intake_cv(
    file: UploadFile = File(...),
    consent: bool = Form(False),
    candidate_id: str | None = Form(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Unggah CV (PDF/DOCX/scan/foto) → pipeline ekstraksi → draft profil."""
    intake = await service.intake_cv(
        db, user=user, file=file, candidate_id=candidate_id, consent=consent
    )
    return service.serialize_intake(db, intake)


@router.get("/intake/{intake_id}")
def get_intake(intake_id: str, db: Session = Depends(get_db)):
    return service.get_intake(db, intake_id)


@router.post("/intake/{intake_id}/review")
def review_intake(
    intake_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Koreksi recruiter atas draft + tandai kelompok field sudah dicek."""
    corrections = (payload or {}).get("corrections") or {}
    reviewed = (payload or {}).get("reviewed") or []
    intake = service.review_intake(
        db, user=user, intake_id=intake_id, corrections=corrections, reviewed=reviewed
    )
    return service.serialize_intake(db, intake)


@router.post("/intake/{intake_id}/finalize")
def finalize_intake(intake_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Finalisasi → render CV standar versi baru (PDF)."""
    intake = service.finalize_intake(db, user=user, intake_id=intake_id)
    return service.serialize_intake(db, intake)


@router.post("/intake/{intake_id}/reprocess")
def reprocess_intake(intake_id: str, db: Session = Depends(get_db)):
    """Jalankan ulang pipeline dengan skema/prompt terkini."""
    intake = service.reprocess_intake(db, intake_id=intake_id)
    return service.serialize_intake(db, intake)


@router.get("/cv-versions/{version_id}/download")
def download_version(version_id: str, db: Session = Depends(get_db)):
    data, name = service.download_version(db, version_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/candidates/{candidate_id}/forget")
def forget_candidate(
    candidate_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Hak hapus atas permintaan subjek data (UU PDP, PRD §10.5)."""
    return service.forget_candidate(db, user=user, candidate_id=candidate_id)


@router.get("/branding")
def get_branding(db: Session = Depends(get_db)):
    return service.serialize_branding(service.get_branding(db))


@router.get("/branding/logo/download")
def download_logo(db: Session = Depends(get_db)):
    """Unduh logo branding (dipakai <img> preview & render PDF)."""
    from fastapi import HTTPException
    from fastapi.responses import Response

    branding = service.get_branding(db)
    if not branding.logo_object_key:
        raise HTTPException(status_code=404, detail="Logo belum diunggah")
    from app.core import storage

    data = storage.get_object(branding.logo_object_key)
    mime = "image/png" if branding.logo_object_key.endswith(".png") else "image/jpeg"
    return Response(content=data, media_type=mime)


# Konfigurasi branding hanya admin/management.
branding_admin_router = APIRouter(
    prefix="/talentpool",
    tags=["talentpool"],
    dependencies=[Depends(get_current_user), Depends(require_roles("admin", "management"))],
)


@branding_admin_router.put("/branding")
def update_branding(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    b = service.update_branding(db, user=user, payload=payload or {})
    return service.serialize_branding(b)


@branding_admin_router.post("/branding/logo", status_code=201)
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Unggah logo perusahaan untuk header CV standar (PNG/JPEG ≤ 2 MB)."""
    data = await file.read()
    b = service.upload_branding_logo(
        db, user=user, data=data, mime=(file.content_type or "").lower()
    )
    return service.serialize_branding(b)


@branding_admin_router.delete("/branding/logo", status_code=204)
def remove_logo(db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.remove_branding_logo(db, user=user)
