"""Job Portal — kandidat apply publik ke Job Order (PRD v3.1 Patch 5).

Guest-apply tanpa akun (kandidat AEOS tidak pernah punya akun `User`,
ikut pola `invite_token` yang sudah dipakai di tempat lain). Portal
diakses per-tenant lewat `{tenant_slug}` di URL — sejalan sifat
white-label AEOS, bukan satu marketplace gabungan lintas-tenant.

Konteks tenant: endpoint publik tidak punya JWT sama sekali, jadi
`core.tenancy.get_tenant()` selalu None di titik masuk. Saat None, filter
tenant otomatis (`do_orm_execute` di core/tenancy.py) TIDAK diterapkan
sama sekali — query jadi lintas-tenant sampai `set_tenant(...)` dipanggil
eksplisit. Pola ini sudah dipakai `payroll/service.py::decide_by_token`
(lookup token dulu tanpa konteks, baru set_tenant sebelum operasi
tenant-scoped) — diikuti persis di sini.
"""

from __future__ import annotations

import json
import secrets

from app.core.database import parse_uuid
from app.core.tenancy import get_tenant, set_tenant
from app.modules import audit
from app.modules.job_portal.schemas import (
    ApplicationStatusOut,
    ApplyIn,
    JobApplicationOut,
    PublicJobOrderDetailOut,
    PublicJobOrderOut,
)
from app.modules.platform.models import Tenant, TenantStatus
from app.modules.recruitment.models import (
    Candidate,
    JobOrder,
    JobOrderBusinessStatus,
    Placement,
    PlacementStatus,
)
from app.modules.recruitment.schemas import ScreeningQuestion
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

_STATUS_LABELS: dict[PlacementStatus, str] = {
    PlacementStatus.sourced: "Lamaran diterima",
    PlacementStatus.screening: "Sedang diperiksa kualifikasinya",
    PlacementStatus.interview_internal: "Proses interview dengan tim rekrutmen",
    PlacementStatus.submitted: "Sedang diproses tim rekrutmen",
    PlacementStatus.sent_to_client: "Sedang direview klien",
    PlacementStatus.client_screening: "Sedang diperiksa klien",
    PlacementStatus.interview_client: "Proses interview dengan klien",
    PlacementStatus.ojt: "Menjalani on-job training",
    PlacementStatus.proposed: "Menunggu konfirmasi penawaran",
    PlacementStatus.accepted: "Penawaran diterima",
    PlacementStatus.onboarded: "Sudah bergabung",
    PlacementStatus.rejected: "Tidak lolos seleksi kali ini",
    PlacementStatus.cancelled: "Lamaran dibatalkan",
}


def _resolve_tenant(db: Session, tenant_slug: str) -> Tenant:
    tenant = db.execute(select(Tenant).where(Tenant.slug == tenant_slug)).scalar_one_or_none()
    if tenant is None or tenant.status != TenantStatus.active:
        raise HTTPException(status_code=404, detail="Halaman karir tidak ditemukan")
    return tenant


def _client_label(jo: JobOrder) -> str:
    return jo.public_client_label or "Klien Konfidensial"


def _to_public_out(jo: JobOrder) -> PublicJobOrderOut:
    return PublicJobOrderOut(
        id=jo.id,
        title=jo.title,
        client_label=_client_label(jo),
        area=jo.area,
        gross_salary=float(jo.gross_salary) if jo.gross_salary else None,
        salary_min=float(jo.salary_min) if jo.salary_min else None,
        salary_max=float(jo.salary_max) if jo.salary_max else None,
        contract_duration_months=jo.contract_duration_months,
        headcount=jo.headcount,
        requirements=jo.requirements,
        question_count=len(jo.screening_questions),
    )


def _get_public_job_order_row(db: Session, jo_id: str) -> JobOrder:
    jo = db.get(JobOrder, parse_uuid(jo_id))
    if jo is None or not jo.is_public or jo.business_status != JobOrderBusinessStatus.open:
        raise HTTPException(status_code=404, detail="Lowongan tidak ditemukan")
    return jo


def list_public_job_orders(db: Session, tenant_slug: str) -> list[PublicJobOrderOut]:
    tenant = _resolve_tenant(db, tenant_slug)
    set_tenant(tenant.id)
    stmt = (
        select(JobOrder)
        .where(
            JobOrder.is_public.is_(True),
            JobOrder.business_status == JobOrderBusinessStatus.open,
        )
        .order_by(JobOrder.created_at.desc())
    )
    return [_to_public_out(jo) for jo in db.execute(stmt).scalars()]


def get_public_job_order(db: Session, tenant_slug: str, jo_id: str) -> PublicJobOrderDetailOut:
    tenant = _resolve_tenant(db, tenant_slug)
    set_tenant(tenant.id)
    jo = _get_public_job_order_row(db, jo_id)
    base = _to_public_out(jo)
    return PublicJobOrderDetailOut(
        **base.model_dump(),
        description=jo.description,
        screening_questions=[ScreeningQuestion(**q) for q in jo.screening_questions],
    )


async def apply_to_job_order(
    db: Session, tenant_slug: str, jo_id: str, payload: ApplyIn, file: UploadFile
) -> JobApplicationOut:
    if not payload.consent:
        raise HTTPException(
            status_code=422, detail="Persetujuan pemrosesan data pribadi (UU PDP) wajib dicentang"
        )
    tenant = _resolve_tenant(db, tenant_slug)
    set_tenant(tenant.id)
    jo = _get_public_job_order_row(db, jo_id)

    email = payload.email.strip().lower()
    candidate = db.execute(select(Candidate).where(Candidate.email == email)).scalar_one_or_none()
    if candidate is None:
        candidate = Candidate(
            full_name=payload.full_name.strip()[:255],
            email=email,
            phone=(payload.phone or "").strip()[:60] or None,
            source="job_portal",
        )
        db.add(candidate)
        db.flush()

    # `Placement` punya UniqueConstraint(candidate_id, job_order_id) — kandidat
    # yang sama TIDAK BOLEH dapat baris kedua utk JO yang sama, baik itu
    # lamaran portal berulang MAUPUN kandidat yang sudah lebih dulu disourcing
    # via Talent Pool internal (placement lama tanpa application_token).
    # Dua-duanya ditangani sebagai satu kasus: reuse baris, backfill token
    # kalau belum ada, jangan pernah INSERT baris kedua.
    existing = db.execute(
        select(Placement).where(
            Placement.candidate_id == candidate.id,
            Placement.job_order_id == jo.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if not existing.application_token:
            existing.application_token = secrets.token_urlsafe(32)
            db.commit()
            db.refresh(existing)
        return JobApplicationOut(
            application_token=existing.application_token,  # type: ignore[arg-type]
            message="Anda sudah terdaftar untuk posisi ini — gunakan token ini untuk cek status.",
        )

    from app.modules.talentpool.service import intake_cv

    await intake_cv(db, user=None, file=file, candidate_id=str(candidate.id), consent=True)

    answers_json = json.dumps(payload.screening_answers) if payload.screening_answers else None
    placement = Placement(
        candidate_id=candidate.id,
        job_order_id=jo.id,
        application_token=secrets.token_urlsafe(32),
        screening_answers=answers_json,
    )
    db.add(placement)
    db.commit()
    db.refresh(placement)
    audit.log_event(
        db,
        action="job_portal.applied",
        entity_type="placement",
        entity_id=placement.id,
        tenant_id=tenant.id,
        detail={"job_order_id": str(jo.id), "candidate_email": email},
    )
    return JobApplicationOut(
        application_token=placement.application_token,  # type: ignore[arg-type]
        message="Lamaran Anda berhasil dikirim. Simpan token ini untuk cek status lamaran Anda.",
    )


def get_application_status(db: Session, token: str) -> ApplicationStatusOut:
    """Tanpa tenant_slug — cari lintas-tenant dulu (konteks belum ada di
    titik ini), baru set_tenant setelah baris ditemukan."""
    placement = db.execute(
        select(Placement).where(Placement.application_token == token)
    ).scalar_one_or_none()
    if placement is None:
        raise HTTPException(status_code=404, detail="Token lamaran tidak ditemukan")

    prev_tenant = get_tenant()
    set_tenant(placement.tenant_id)
    try:
        candidate = db.get(Candidate, placement.candidate_id)
        jo = db.get(JobOrder, placement.job_order_id)
        if candidate is None or jo is None:
            raise HTTPException(status_code=404, detail="Data lamaran tidak lengkap")
        return ApplicationStatusOut(
            job_title=jo.title,
            candidate_name=candidate.full_name,
            status_label=_STATUS_LABELS.get(placement.status, placement.status.value),
            submitted_at=placement.created_at,
        )
    finally:
        set_tenant(prev_tenant)
