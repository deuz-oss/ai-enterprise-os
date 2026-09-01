import base64
import json
import math
from datetime import UTC, date, timedelta, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import parse_uuid
from app.core.llm import ai_configured, chat_completion, embed_texts, vision_completion
from app.modules import audit
from app.modules.clients.models import Client
from app.modules.recruitment.models import (
    Candidate,
    CandidateStatus,
    InterviewSchedule,
    JobOrder,
    JobOrderBusinessStatus,
    JobOrderStatus,
    Placement,
    PlacementStatus,
)
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateUpdate,
    InterviewScheduleCreate,
    InterviewScheduleUpdate,
    JobOrderCreate,
    JobOrderUpdate,
    OfferingSendIn,
    PlacementCreate,
)
from app.modules.talentpool.models import CvIntake

# ---------- Job orders ----------


def _get_job_order(db: Session, jo_id: str) -> JobOrder:
    jo = db.get(JobOrder, parse_uuid(jo_id))
    if jo is None:
        raise HTTPException(status_code=404, detail="Job order tidak ditemukan")
    return jo


def _generate_request_id(db: Session) -> str:
    """JO/{tahun}/{urutan berjalan} — ikut pola EMP-0001/INV/{tahun}/0001 yang sudah ada."""
    count = db.scalar(select(func.count(JobOrder.id))) or 0
    return f"JO/{date.today().year}/{count + 1:04d}"


def create_job_order(db: Session, payload: JobOrderCreate) -> JobOrder:
    if db.get(Client, parse_uuid(payload.client_id)) is None:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    data = payload.model_dump()
    if not data.get("request_id"):
        data["request_id"] = _generate_request_id(db)
    if not data.get("request_date"):
        data["request_date"] = date.today()
    # `screening_questions` itu properti read-only (turunan JSON) di model —
    # simpan ke kolom mentahnya, bukan lewat nama atribut yang sama.
    questions = data.pop("screening_questions", None)
    data["screening_questions_json"] = json.dumps(questions) if questions else None
    jo = JobOrder(**data)
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


def list_stale_job_orders(db: Session) -> list[JobOrder]:
    """JO business_status=dibuka dan request_date >= 30 hari lalu (PRD v3.1 Patch 3)."""
    stmt = (
        select(JobOrder)
        .where(JobOrder.business_status == JobOrderBusinessStatus.open)
        .order_by(JobOrder.request_date)
    )
    return [jo for jo in db.execute(stmt).scalars() if jo.is_stale]


def get_job_order(db: Session, jo_id: str) -> JobOrder:
    return _get_job_order(db, jo_id)


def update_job_order(db: Session, jo_id: str, payload: JobOrderUpdate) -> JobOrder:
    jo = _get_job_order(db, jo_id)
    data = payload.model_dump(exclude_unset=True)
    if "screening_questions" in data:
        questions = data.pop("screening_questions")
        jo.screening_questions_json = json.dumps(questions) if questions else None
    for field, value in data.items():
        setattr(jo, field, value)
    db.commit()
    db.refresh(jo)
    return jo


def delete_job_order(db: Session, jo_id: str) -> None:
    jo = _get_job_order(db, jo_id)
    db.delete(jo)
    db.commit()


def job_order_document_download_url(db: Session, jo_id: str) -> str:
    jo = _get_job_order(db, jo_id)
    if not jo.source_document_object_key:
        raise HTTPException(status_code=404, detail="Job order ini tidak punya dokumen sumber")
    audit.log_event(
        db,
        action="job_order_document.download_url",
        entity_type="job_order",
        entity_id=jo.id,
        detail={"file_name": jo.source_document_file_name},
    )
    return storage.presigned_get_url(jo.source_document_object_key)


# ---------- Ekstraksi dokumen Job Order / Manpower Requisition (PRD v3.1 Patch 3b) ----------

_JO_ALLOWED_MIME = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/webp",
)
_JO_MAX_BYTES = 10 * 1024 * 1024

_JO_EXTRACTION_PROMPT = (
    "Anda mesin ekstraksi dokumen Job Order / Manpower Requisition dari perusahaan "
    "outsourcing Indonesia. Baca dokumen dan kembalikan HANYA JSON sesuai skema tetap "
    "berikut:\n"
    "{\n"
    '  "requisition_code": string|null,\n'
    '  "job_title": string|null,\n'
    '  "client_name": string|null,\n'
    '  "area_location": string|null,\n'
    '  "headcount": number|null,\n'
    '  "request_effective_date": "YYYY-MM-DD"|null,\n'
    '  "contract_start_date": "YYYY-MM-DD"|null,\n'
    '  "contract_end_date": "YYYY-MM-DD"|null,\n'
    '  "gross_basic_salary": number|null,\n'
    '  "mandatory_criteria": [string],\n'
    '  "preferred_criteria": [string],\n'
    '  "job_description_summary": string|null\n'
    "}\n"
    "Gunakan null/[] untuk data yang tidak ada. Jangan mengarang angka atau tanggal. "
    "gross_basic_salary hanya angka gaji pokok bulanan (bukan total dengan tunjangan)."
)


def _jo_doc_kind(data: bytes, file_name: str, mime_type: str) -> str:
    """Reuse deteksi jenis dokumen dari talentpool — bukan duplikasi logic."""
    from app.modules.talentpool.models import CvDocKind
    from app.modules.talentpool.service import detect_doc_kind

    kind = detect_doc_kind(data, file_name, mime_type)
    return kind.value if isinstance(kind, CvDocKind) else str(kind)


async def extract_job_order_document(db: Session, file: UploadFile) -> dict:
    """Upload dokumen JO -> ekstraksi AI one-shot -> saran field (BELUM buat JobOrder).

    Beda dari CV Intake: dokumen ini bukan sumber yang butuh alur review
    berjenjang — user me-review langsung di form create JO, jadi cukup
    ekstraksi sekali pakai. Dokumen tetap disimpan (utk viewer di kolom
    Request ID) via object_key yang dikembalikan.
    """
    mime = (file.content_type or "").lower()
    if mime not in _JO_ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="Format dokumen harus PDF, DOCX, atau gambar")
    data = await file.read()
    if len(data) > _JO_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Ukuran dokumen maksimal 10 MB")

    kind = _jo_doc_kind(data, file.filename or "job-order.pdf", mime)
    if kind in ("pdf_scan", "image"):
        img_mime = "image/png" if kind == "image" else "application/pdf"
        raw = vision_completion(
            _JO_EXTRACTION_PROMPT,
            "Ekstrak data Job Order dari dokumen hasil scan ini.",
            image_b64=base64.b64encode(data).decode(),
            mime_type=img_mime,
            feature="recruitment.jo_intake",
        )
    else:
        from app.modules.talentpool.service import _docx_text, _pdf_text

        text = _docx_text(data) if kind == "docx" else _pdf_text(data)
        raw = chat_completion(
            _JO_EXTRACTION_PROMPT,
            f"DOKUMEN JOB ORDER:\n{text[:24000]}",
            feature="recruitment.jo_intake",
        )
    parsed = raw if isinstance(raw, dict) else {}

    contract_start = _safe_date_str(parsed.get("contract_start_date"))
    contract_end = _safe_date_str(parsed.get("contract_end_date"))
    duration_months = None
    if contract_start and contract_end:
        start_d, end_d = date.fromisoformat(contract_start), date.fromisoformat(contract_end)
        if end_d > start_d:
            duration_months = round((end_d - start_d).days / 30.44) or 1

    object_key = storage.new_object_key("job-order-docs", file.filename or "job-order.pdf")
    storage.put_object(object_key, data, mime)

    return {
        "object_key": object_key,
        "file_name": (file.filename or "job-order.pdf")[:255],
        "requisition_code": str(parsed.get("requisition_code") or "").strip()[:50] or None,
        "job_title": str(parsed.get("job_title") or "").strip()[:255] or None,
        "client_name": str(parsed.get("client_name") or "").strip()[:255] or None,
        "area_location": str(parsed.get("area_location") or "").strip()[:120] or None,
        "headcount": _safe_int(parsed.get("headcount")),
        "request_effective_date": _safe_date_str(parsed.get("request_effective_date")),
        "contract_start_date": contract_start,
        "contract_end_date": contract_end,
        "contract_duration_months": duration_months,
        "gross_basic_salary": _safe_float(parsed.get("gross_basic_salary")),
        "mandatory_criteria": _clean_str_list(parsed.get("mandatory_criteria")),
        "preferred_criteria": _clean_str_list(parsed.get("preferred_criteria")),
        "job_description_summary": str(parsed.get("job_description_summary") or "").strip()[:2000]
        or None,
    }


def _clean_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(c).strip()[:300] for c in value if str(c).strip()]


def _safe_date_str(value) -> str | None:
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> float | None:
    try:
        return round(float(value), 2) if value is not None else None
    except (TypeError, ValueError):
        return None


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
    # PRD v3.1 Patch 2: Placement sekarang dibuat sejak sourcing (status default
    # `sourced`), bukan lagi saat siap ditawari — kandidat baru masuk tahap
    # screening, belum interview.
    candidate.status = CandidateStatus.screening
    if jo.status == JobOrderStatus.open:
        jo.status = JobOrderStatus.screening
    db.commit()
    db.refresh(placement)
    # PRD v3.0 auto prospek→aktif: placement pertama untuk client ini → client aktif
    try:
        from datetime import datetime

        from app.modules.clients.models import ClientStatus

        client = db.get(Client, jo.client_id)
        if client and client.status != ClientStatus.active:
            existing_active = (
                db.execute(
                    select(Placement)
                    .join(JobOrder, Placement.job_order_id == JobOrder.id)
                    .where(
                        JobOrder.client_id == client.id,
                        Placement.status != PlacementStatus.cancelled,
                    )
                )
                .scalars()
                .first()
            )
            if existing_active and existing_active.id == placement.id:
                client.status = ClientStatus.active
                try:
                    client.activated_at = datetime.now(UTC)
                except Exception:
                    pass
                audit.log_event(
                    db,
                    action="client.auto_activated",
                    entity_type="client",
                    entity_id=str(client.id),
                    detail={"placement_id": str(placement.id)},
                )
                db.commit()
    except Exception:
        pass
    # Fase 13: kunci versi CV standar terbaru sebagai bukti submission (§10.3).
    try:
        from app.modules.talentpool.service import lock_version_for_placement

        lock_version_for_placement(db, candidate_id=candidate.id, placement_id=placement.id)
    except Exception:
        pass
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
    db: Session,
    placement_id: str,
    new_status: PlacementStatus,
    ojt_start_date: date | None = None,
    ojt_end_date: date | None = None,
) -> Placement:
    placement = db.get(Placement, parse_uuid(placement_id))
    if placement is None:
        raise HTTPException(status_code=404, detail="Placement tidak ditemukan")
    placement.status = new_status
    if ojt_start_date is not None:
        placement.ojt_start_date = ojt_start_date
    if ojt_end_date is not None:
        placement.ojt_end_date = ojt_end_date
    candidate = db.get(Candidate, placement.candidate_id)
    jo = db.get(JobOrder, placement.job_order_id)
    if candidate and jo:
        if new_status in (
            PlacementStatus.interview_internal,
            PlacementStatus.interview_client,
        ):
            candidate.status = CandidateStatus.interview
        elif new_status == PlacementStatus.proposed:
            candidate.status = CandidateStatus.offered
        elif new_status == PlacementStatus.onboarded:
            candidate.status = CandidateStatus.placed
            active = db.execute(
                select(Placement).where(
                    Placement.job_order_id == jo.id,
                    Placement.status == PlacementStatus.onboarded,
                )
            ).scalars()
            if len(list(active)) >= jo.headcount:
                jo.status = JobOrderStatus.filled
        elif new_status in (
            PlacementStatus.cancelled,
            PlacementStatus.rejected,
        ) and candidate.status in (
            CandidateStatus.screening,
            CandidateStatus.interview,
            CandidateStatus.offered,
        ):
            candidate.status = CandidateStatus.rejected
    db.commit()
    db.refresh(placement)
    return placement


def _get_placement(db: Session, placement_id: str) -> Placement:
    placement = db.get(Placement, parse_uuid(placement_id))
    if placement is None:
        raise HTTPException(status_code=404, detail="Placement tidak ditemukan")
    return placement


def _offering_letter_pdf(
    db: Session,
    placement: Placement,
    candidate: Candidate,
    jo: JobOrder,
    client: Client,
    offered_salary: float,
) -> bytes:
    """PDF surat penawaran kerja dibrandingi tenant — PRD v3.0 §4 aksi "Offering"."""
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    from app.modules.platform.models import Tenant

    tenant = db.get(Tenant, placement.tenant_id)
    tenant_name = tenant.name if tenant else "-"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Surat Penawaran Kerja - {candidate.full_name}",
    )
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontSize = 10
    normal.leading = 15

    today = date.today().strftime("%d %B %Y")
    start = (
        placement.start_date.strftime("%d %B %Y") if placement.start_date else "menyusul konfirmasi"
    )

    story = [
        Paragraph(f"<b>{tenant_name}</b>", styles["Heading2"]),
        Spacer(1, 4),
        Paragraph(f"{today}", normal),
        Spacer(1, 14),
        Paragraph("<b>SURAT PENAWARAN KERJA</b>", styles["Heading3"]),
        Spacer(1, 10),
        Paragraph(f"Kepada Yth. <b>{candidate.full_name}</b>", normal),
        Spacer(1, 10),
        Paragraph(
            f"Dengan hormat, sehubungan dengan proses rekrutmen untuk posisi "
            f"<b>{jo.title}</b> pada klien <b>{client.name}</b>, dengan ini kami "
            f"sampaikan penawaran bekerja dengan rincian sebagai berikut:",
            normal,
        ),
        Spacer(1, 8),
        Table(
            [
                ["Posisi", ": " + jo.title],
                ["Penempatan (Klien)", ": " + client.name],
                ["Gaji Ditawarkan", f": Rp {offered_salary:,.0f} / bulan"],
                ["Perkiraan Tanggal Mulai", ": " + start],
            ],
            colWidths=[50 * mm, 105 * mm],
        ),
        Spacer(1, 14),
        Paragraph(
            "Mohon konfirmasi kesediaan Anda dengan menandatangani surat ini secara "
            "elektronik. Rincian lengkap syarat &amp; ketentuan kerja akan dituangkan "
            "dalam kontrak kerja setelah penawaran ini diterima.",
            normal,
        ),
        Spacer(1, 20),
        Paragraph(f"Hormat kami,<br/>{tenant_name}", normal),
    ]
    doc.build(story)
    return buf.getvalue()


def send_offering_letter(db: Session, placement_id: str, payload: OfferingSendIn):
    """PRD v3.0 §4 aksi 2/3 "Offering": surat penawaran PDF -> status offered -> esign."""
    from app.modules.esign.service import send_placement_offering

    placement = _get_placement(db, placement_id)
    candidate = _get_candidate(db, str(placement.candidate_id))
    jo = _get_job_order(db, str(placement.job_order_id))
    client = db.get(Client, jo.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Klien job order tidak ditemukan")

    if payload.offered_salary is not None:
        placement.offered_salary = payload.offered_salary
    if payload.start_date is not None:
        placement.start_date = payload.start_date
    if placement.offered_salary is None:
        raise HTTPException(
            status_code=422, detail="Gaji yang ditawarkan wajib diisi sebelum kirim penawaran"
        )

    pdf_bytes = _offering_letter_pdf(
        db, placement, candidate, jo, client, float(placement.offered_salary)
    )
    file_name = f"offering-{placement.id}.pdf"
    object_key = storage.new_object_key(f"offerings/{placement.id}", file_name)
    storage.put_object(object_key, pdf_bytes, "application/pdf")
    placement.offering_letter_object_key = object_key

    request = send_placement_offering(
        db,
        placement.id,
        pdf_bytes=pdf_bytes,
        file_name=file_name,
        title=f"Surat Penawaran Kerja - {candidate.full_name} - {jo.title}",
        signer_name=payload.signer_name,
        signer_email=payload.signer_email,
    )

    candidate.status = CandidateStatus.offered
    # PRD v3.1 Patch 2: sebelum ini Placement dibuat langsung dgn status
    # default `proposed`, jadi tidak perlu transisi eksplisit di sini. Sekarang
    # default-nya `sourced` -> wajib set eksplisit, kalau tidak placement tidak
    # akan pernah maju ke `proposed` meski surat penawaran sudah terkirim.
    placement.status = PlacementStatus.proposed
    if jo.status in (JobOrderStatus.open, JobOrderStatus.screening, JobOrderStatus.interview):
        jo.status = JobOrderStatus.offering
    db.commit()
    audit.log_event(
        db,
        action="recruitment.offering_sent",
        entity_type="placement",
        entity_id=placement.id,
        detail={"candidate_id": str(candidate.id), "job_order_id": str(jo.id)},
    )
    return request


def offering_summary(db: Session) -> dict:
    """Ringkasan pipeline offering — dipakai widget "Offering" Talent Cloud.

    "Aktif" = surat penawaran sudah dibuat (`offering_letter_object_key` terisi).
    "Menunggu ttd" = permintaan TTE-nya masih berstatus terkirim/dilihat (belum
    ditandatangani/ditolak/kedaluwarsa). Ambil `EsignRequest` TERBARU per placement
    (bisa lebih dari satu kalau pernah expired/declined lalu dikirim ulang).
    """
    from app.modules.esign.models import EsignRequest, EsignStatus

    placements = (
        db.execute(select(Placement).where(Placement.offering_letter_object_key.is_not(None)))
        .scalars()
        .all()
    )
    items: list[dict] = []
    awaiting = 0
    for placement in placements:
        candidate = db.get(Candidate, placement.candidate_id)
        jo = db.get(JobOrder, placement.job_order_id)
        if candidate is None or jo is None:
            continue
        client = db.get(Client, jo.client_id)
        latest_request = db.scalars(
            select(EsignRequest)
            .where(EsignRequest.placement_id == placement.id)
            .order_by(EsignRequest.created_at.desc())
            .limit(1)
        ).first()
        esign_status = latest_request.status.value if latest_request else None
        if latest_request and latest_request.status in (EsignStatus.sent, EsignStatus.viewed):
            awaiting += 1
        items.append(
            {
                "placement_id": placement.id,
                "candidate_name": candidate.full_name,
                "job_order_title": jo.title,
                "client_name": client.name if client else "-",
                "offered_salary": (
                    float(placement.offered_salary)
                    if placement.offered_salary is not None
                    else None
                ),
                "esign_status": esign_status,
            }
        )
    items.sort(key=lambda i: i["candidate_name"])
    return {"total_active": len(items), "awaiting_signature": awaiting, "items": items}


# ---------- Interview Schedules — PRD v3.0 Talent Cloud ----------


def create_interview(
    db: Session, payload: InterviewScheduleCreate, created_by=None
) -> InterviewSchedule:
    candidate = _get_candidate(db, str(payload.candidate_id))
    jo = _get_job_order(db, str(payload.job_order_id))
    sched = InterviewSchedule(
        candidate_id=candidate.id,
        job_order_id=jo.id,
        interviewer_id=payload.interviewer_id,
        scheduled_at=payload.scheduled_at,
        location=payload.location,
        meeting_url=payload.meeting_url,
        interview_type=payload.interview_type,
        created_by=created_by,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    try:
        audit.log_event(
            db,
            action="interview.scheduled",
            entity_type="job_order",
            entity_id=str(jo.id),
            detail={"candidate_id": str(candidate.id), "scheduled_at": str(sched.scheduled_at)},
        )
    except Exception:
        pass
    _notify_interview_scheduled(db, jo=jo, candidate=candidate, sched=sched)
    return sched


def _notify_interview_scheduled(db: Session, *, jo, candidate, sched) -> None:
    """Notif in-app + email ke interviewer + pesan sistem di channel JO
    (PRD v3.0 §4). Best-effort — kegagalan notifikasi tidak boleh
    mematahkan penjadwalan interview yang sudah tersimpan.

    `scheduled_at` tersimpan UTC (aware); ditampilkan dalam WIB (UTC+7,
    tanpa DST) karena teks ini dibaca langsung oleh recruiter, bukan
    di-render ulang di frontend seperti field API lain.
    """
    scheduled_at = sched.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)
    local_dt = scheduled_at.astimezone(timezone(timedelta(hours=7)))
    when = local_dt.strftime("%d %b %Y %H:%M") + " WIB"
    if sched.interviewer_id:
        try:
            from app.modules.notifications.service import notify

            notify(
                db,
                user_id=sched.interviewer_id,
                title=f"Interview dijadwalkan: {candidate.full_name}",
                body=f"JO {jo.title} — {when}" + (f" · {sched.location}" if sched.location else ""),
                category="interview",
                entity_type="interview_schedule",
                entity_id=sched.id,
            )
        except Exception:
            pass
    try:
        from app.modules.chat.models import ChatMessage
        from app.modules.chat.service import ensure_job_order_channel

        ch = ensure_job_order_channel(db, jo)
        if ch:
            db.add(
                ChatMessage(
                    channel_id=ch.id,
                    sender_id=ch.created_by_id,
                    content=(
                        f"📅 Interview dijadwalkan untuk {candidate.full_name} — {when}"
                        + (f" di {sched.location}" if sched.location else "")
                    ),
                    message_type="system",
                    tenant_id=ch.tenant_id,
                )
            )
            db.commit()
    except Exception:
        db.rollback()


def list_interviews(db: Session, job_order_id: str | None = None) -> list[InterviewSchedule]:
    stmt = select(InterviewSchedule).order_by(InterviewSchedule.scheduled_at.desc())
    if job_order_id:
        stmt = stmt.where(InterviewSchedule.job_order_id == parse_uuid(job_order_id))
    return list(db.execute(stmt).scalars())


def update_interview(
    db: Session, interview_id: str, payload: InterviewScheduleUpdate
) -> InterviewSchedule:
    sched = db.get(InterviewSchedule, parse_uuid(interview_id))
    if not sched:
        raise HTTPException(status_code=404, detail="Interview tidak ditemukan")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sched, field, value)
    db.commit()
    db.refresh(sched)
    return sched


# ---------- AI Matching Native — PRD v3.0 Talent Cloud ----------


def _candidate_profile(db: Session, candidate: Candidate) -> dict:
    """Profil kandidat untuk matching, sumber utama `CvIntake.extracted` JSON
    terstruktur (menutup gap audit `ai/service.py:64` — bukan `cv_text` mentah),
    fallback field `Candidate` mentah bila belum ada intake."""
    intake = db.execute(
        select(CvIntake)
        .where(CvIntake.candidate_id == candidate.id, CvIntake.extracted.is_not(None))
        .order_by(CvIntake.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    data: dict = {}
    if intake and intake.extracted:
        try:
            data = json.loads(intake.extracted)
        except (json.JSONDecodeError, TypeError):
            data = {}

    skills = [str(s) for s in (data.get("skills") or [])] or (candidate.skills or "").split()
    experience = data.get("experience") or []
    certifications = [
        str(c.get("nama")) for c in (data.get("certifications") or []) if c.get("nama")
    ]
    domisili = data.get("domisili") or candidate.city
    readiness = data.get("readiness") or (intake.readiness if intake else None)
    expected_salary = data.get("expected_salary") or (
        float(candidate.expected_salary) if candidate.expected_salary else None
    )

    text_parts = [data.get("summary") or ""]
    if skills:
        text_parts.append("Skill: " + ", ".join(skills))
    for exp in experience[:5]:
        text_parts.append(
            (
                f"{exp.get('posisi') or ''} di {exp.get('perusahaan') or ''}. "
                f"{exp.get('ringkasan') or ''}"
            ).strip()
        )
    if certifications:
        text_parts.append("Sertifikasi: " + ", ".join(certifications))
    text = "\n".join(p for p in text_parts if p) or candidate.full_name

    return {
        "text": text,
        "skills": [s.lower() for s in skills],
        "domisili": (domisili or "").lower(),
        "readiness": readiness,
        "expected_salary": expected_salary,
        "certifications": [c.lower() for c in certifications],
    }


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _rule_bonus(jo: JobOrder, profile: dict) -> int:
    bonus = 0
    jo_blob = f"{jo.title or ''} {jo.requirements or ''}".lower()
    if profile["domisili"] and profile["domisili"] in jo_blob:
        bonus += 8
    if profile["readiness"] == "segera":
        bonus += 5
    elif profile["readiness"] == "n_minggu":
        bonus += 2
    salary = profile["expected_salary"]
    if salary and jo.salary_min and jo.salary_max:
        try:
            if float(jo.salary_min) <= float(salary) <= float(jo.salary_max):
                bonus += 7
        except (TypeError, ValueError):
            pass
    return bonus


def _missing_requirements(jo: JobOrder, profile: dict) -> list[str]:
    missing: list[str] = []
    if jo.requirements and "k3" in jo.requirements.lower():
        blob = " ".join(profile["skills"] + profile["certifications"])
        if "k3" not in blob:
            missing.append("sertifikasi K3")
    return missing


def _llm_rerank_explain(jo: JobOrder, entries: list[tuple[Candidate, dict]]) -> dict:
    """Satu panggilan LLM untuk explain top kandidat (PRD §4 — LLM rerank).
    Gagal apapun (AI belum dikonfigurasi/provider error) → dict kosong,
    caller fallback ke explain deterministik. Tidak boleh mematahkan matching."""
    if not entries:
        return {}
    system = (
        "Anda asisten rekrutmen. Untuk tiap kandidat, jelaskan singkat (<=15 kata, "
        "Bahasa Indonesia) mengapa cocok untuk job order ini berdasarkan profil yang diberikan. "
        'Balas HANYA JSON: {"explanations": {"<candidate_id>": "<alasan singkat>"}}'
    )
    user_payload = {
        "job_order": {"title": jo.title, "requirements": jo.requirements},
        "candidates": [
            {
                "candidate_id": str(cand.id),
                "skills": profile["skills"][:10],
                "text": profile["text"][:500],
            }
            for cand, profile in entries
        ],
    }
    try:
        result = chat_completion(
            system,
            json.dumps(user_payload, ensure_ascii=False),
            feature="recruitment.match_explain",
        )
        explanations = result.get("explanations", {}) if isinstance(result, dict) else {}
        return {str(k): str(v) for k, v in explanations.items()}
    except Exception:  # noqa: BLE001 - AI rerank tidak boleh mematahkan matching
        return {}


def match_candidates(
    db: Session, job_order_id: str, top_k: int = 50, *, billable: bool = False
) -> list[dict]:
    """Matching native 0-100: embedding cosine (bila AI aktif) + rules
    (domisili, readiness, expected_salary) + LLM rerank explain untuk top hasil.
    Fallback deterministik (skills overlap) bila AI belum dikonfigurasi/gagal.

    `billable=True` (dipanggil dari POST /match) mencatat audit event
    `recruitment.match_executed` — sumber hitung metered 2k/match (PRD v3.0
    §2). GET /matches (filter min_score) sengaja tidak dihitung: tanpa cache
    hasil, endpoint itu mengeksekusi ulang algoritma yang sama tiap panggilan
    — menghitungnya sebagai billable akan menagih per-poll, bukan per-JO
    sesuai PRD. Known limitation: begitu hasil match di-cache/disimpan,
    revisit titik ini.
    """
    jo = _get_job_order(db, job_order_id)
    candidates = list(
        db.execute(
            select(Candidate).where(Candidate.status != CandidateStatus.archived).limit(500)
        ).scalars()
    )
    profiles = [_candidate_profile(db, cand) for cand in candidates]

    jo_text = "\n".join(filter(None, [jo.title, jo.description, jo.requirements])) or (
        jo.title or ""
    )
    jo_vec: list[float] | None = None
    cand_vecs: list[list[float]] | None = None
    if ai_configured() and jo_text.strip():
        try:
            vectors = embed_texts(
                [jo_text] + [p["text"] for p in profiles], feature="recruitment.match_embedding"
            )
            jo_vec, cand_vecs = vectors[0], vectors[1:]
        except Exception:  # noqa: BLE001 - AI gagal → fallback heuristik, jangan putus matching
            jo_vec, cand_vecs = None, None

    jo_skills = set((jo.requirements or jo.title or "").lower().split())
    scored: list[tuple[Candidate, int, dict]] = []
    for idx, cand in enumerate(candidates):
        profile = profiles[idx]
        if jo_vec is not None and cand_vecs is not None:
            similarity = max(0.0, _cosine(jo_vec, cand_vecs[idx]))
            base = round(similarity * 80)
        else:
            overlap = len(jo_skills & set(profile["skills"])) if jo_skills else 0
            base = min(80, 50 + overlap * 10) if jo_skills else 50
        score = max(0, min(100, base + _rule_bonus(jo, profile)))
        scored.append((cand, score, profile))

    scored.sort(key=lambda row: row[1], reverse=True)
    top = scored[:top_k]

    explains: dict[str, str] = {}
    if jo_vec is not None and top:
        explains = _llm_rerank_explain(jo, [(cand, profile) for cand, _, profile in top[:10]])

    results: list[dict] = []
    for cand, score, profile in top:
        explain = explains.get(str(cand.id))
        if not explain:
            matched = sorted(jo_skills & set(profile["skills"]))
            explain = f"skill cocok: {', '.join(matched)}" if matched else "kecocokan umum"
        results.append(
            {
                "candidate_id": cand.id,
                "match_score": score,
                "explain": explain,
                "missing": _missing_requirements(jo, profile),
            }
        )
    if billable:
        try:
            audit.log_event(
                db,
                action="recruitment.match_executed",
                entity_type="job_order",
                entity_id=str(jo.id),
                detail={"evaluated": len(candidates), "top_k": top_k},
            )
        except Exception:
            pass
    return results
