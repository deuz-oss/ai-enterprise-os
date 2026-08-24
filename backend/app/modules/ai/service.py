"""Layanan AI Layer fase 6: screening CV otomatis & matching kandidat↔job order.

Hasil penilaian LLM disimpan persisten di tabel ai_screenings sehingga bisa
diaudit dan dipakai ulang (matching tidak menilai ulang pasangan yang sama).
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import chat_completion
from app.core.storage import get_object
from app.modules.ai.models import AIScreening, ScreeningVerdict
from app.modules.ai.schemas import MatchItemOut, MatchResultOut, ScreeningOut
from app.modules.ai.textutils import extract_document_text
from app.modules.recruitment.models import Candidate, CandidateStatus, JobOrder

# Batas karakter CV yang dikirim ke LLM agar prompt tetap wajar.
_MAX_CV_CHARS = 12_000
# Batas kandidat yang dinilai dalam satu kali matching (kendali biaya API).
_MAX_MATCH_CANDIDATES = 15

_ACTIVE_CANDIDATE_STATUSES = (
    CandidateStatus.new,
    CandidateStatus.screening,
    CandidateStatus.interview,
)

_VERDICT_BY_VALUE = {v.value: v for v in ScreeningVerdict}

_SYSTEM_PROMPT = (
    "Anda adalah recruiter senior di perusahaan outsourcing Indonesia. "
    "Tugas Anda menilai kecocokan kandidat terhadap kebutuhan lowongan secara "
    "objektif berdasarkan data yang diberikan. Balas HANYA dengan JSON valid "
    "tanpa teks lain, dengan skema: "
    '{"score": <0-100>, "verdict": "<direkomendasikan|dipertimbangkan|'
    'tidak_direkomendasikan>", "summary": "<ringkasan 2-3 kalimat bahasa '
    'Indonesia>", "strengths": ["<poin kekuatan>"], "risks": ["<poin risiko/kekurangan>"]}. '
    "Skor mencerminkan kecocokan keseluruhan: >=75 direkomendasikan, "
    "50-74 dipertimbangkan, <50 tidak direkomendasikan."
)


def _get_candidate(db: Session, candidate_id: UUID) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Kandidat tidak ditemukan")
    return candidate


def _get_job_order(db: Session, job_order_id: UUID) -> JobOrder:
    job_order = db.get(JobOrder, job_order_id)
    if not job_order:
        raise HTTPException(status_code=404, detail="Job order tidak ditemukan")
    return job_order


def _candidate_block(candidate: Candidate) -> str:
    rows = [
        ("Nama", candidate.full_name),
        ("Pendidikan", candidate.education),
        ("Pengalaman (tahun)", candidate.experience_years),
        ("Perusahaan saat ini", candidate.current_company),
        ("Keahlian", candidate.skills),
        ("Ekspektasi gaji", candidate.expected_salary),
        ("Kota", candidate.city),
        ("Catatan", candidate.notes),
    ]
    lines = [f"- {label}: {value}" for label, value in rows if value is not None]
    return "\n".join(lines) if lines else "- (profil minim)"


def _job_order_block(job_order: JobOrder) -> str:
    salary = ""
    if job_order.salary_min or job_order.salary_max:
        salary = f"\nRentang gaji: {job_order.salary_min or '-'} s/d {job_order.salary_max or '-'}"
    return (
        f"Posisi: {job_order.title}\n"
        f"Jumlah kebutuhan: {job_order.headcount}\n"
        f"Deskripsi: {job_order.description or '-'}\n"
        f"Kualifikasi: {job_order.requirements or '-'}{salary}"
    )


def _normalize_verdict(raw: object, score: int) -> ScreeningVerdict:
    value = str(raw).strip().lower() if raw else ""
    if value in _VERDICT_BY_VALUE:
        return _VERDICT_BY_VALUE[value]
    # Beberapa model mengembalikan versi Inggris; petakan yang umum.
    aliases = {
        "recommended": ScreeningVerdict.recommended,
        "consider": ScreeningVerdict.consider,
        "not recommended": ScreeningVerdict.reject,
        "not_recommended": ScreeningVerdict.reject,
        "rejected": ScreeningVerdict.reject,
    }
    if value in aliases:
        return aliases[value]
    if score >= 75:
        return ScreeningVerdict.recommended
    if score >= 50:
        return ScreeningVerdict.consider
    return ScreeningVerdict.reject


def _string_list(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw][:8]
    return []


def screen_candidate(
    db: Session, candidate_id: UUID, job_order_id: UUID | None = None
) -> AIScreening:
    """Nilai satu kandidat (opsional terhadap job order tertentu) via LLM."""
    candidate = _get_candidate(db, candidate_id)
    job_order = _get_job_order(db, job_order_id) if job_order_id else None
    if not candidate.cv_object_key:
        raise HTTPException(
            status_code=422,
            detail="Kandidat belum memiliki CV. Unggah CV terlebih dahulu.",
        )
    cv_text = extract_document_text(
        get_object(candidate.cv_object_key), candidate.cv_file_name or ""
    )[:_MAX_CV_CHARS]

    target = f"LOWONGAN YANG DITUJU:\n{_job_order_block(job_order)}" if job_order else (
        "Belum ada lowongan spesifik. Nilai kualitas umum kandidat untuk posisi "
        "tenaga kerja outsourcing."
    )
    user_prompt = (
        f"{target}\n\nPROFIL KANDIDAT:\n{_candidate_block(candidate)}\n\n"
        f"ISI CV:\n{cv_text}"
    )

    result = chat_completion(_SYSTEM_PROMPT, user_prompt, json_mode=True)
    data = result if isinstance(result, dict) else {}

    try:
        score = max(0, min(100, int(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    screening = AIScreening(
        candidate_id=candidate.id,
        job_order_id=job_order.id if job_order else None,
        score=score,
        verdict=_normalize_verdict(data.get("verdict"), score),
        summary=str(data.get("summary") or "").strip() or "-",
        strengths_json=json.dumps(_string_list(data.get("strengths")), ensure_ascii=False),
        risks_json=json.dumps(_string_list(data.get("risks")), ensure_ascii=False),
        model=get_settings().ai_model,
    )
    db.add(screening)
    if candidate.status == CandidateStatus.new:
        candidate.status = CandidateStatus.screening
    db.commit()
    db.refresh(screening)
    return screening


def list_screenings(db: Session, candidate_id: UUID) -> list[AIScreening]:
    _get_candidate(db, candidate_id)
    stmt = (
        select(AIScreening)
        .where(AIScreening.candidate_id == candidate_id)
        .order_by(AIScreening.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def match_job_order(db: Session, job_order_id: UUID) -> MatchResultOut:
    """Ranking kandidat aktif untuk sebuah job order.

    Pasangan (kandidat, job order) yang sudah pernah dinilai dipakai ulang,
    jadi menjalankan match berulang tidak memicu panggilan LLM tambahan.
    """
    job_order = _get_job_order(db, job_order_id)
    candidates = list(
        db.scalars(
            select(Candidate)
            .where(Candidate.status.in_(_ACTIVE_CANDIDATE_STATUSES))
            .order_by(Candidate.created_at.desc())
            .limit(_MAX_MATCH_CANDIDATES)
        ).all()
    )

    items: list[MatchItemOut] = []
    reused = 0
    for candidate in candidates:
        existing = db.scalars(
            select(AIScreening)
            .where(AIScreening.candidate_id == candidate.id)
            .where(AIScreening.job_order_id == job_order.id)
            .order_by(AIScreening.created_at.desc())
            .limit(1)
        ).first()
        if existing:
            screening = existing
            reused += 1
        else:
            screening = screen_candidate(db, candidate.id, job_order.id)
        items.append(
            MatchItemOut.model_validate(
                {"candidate": candidate, "screening": ScreeningOut.model_validate(screening)}
            )
        )

    items.sort(key=lambda item: item.screening.score, reverse=True)
    return MatchResultOut(
        job_order_id=job_order.id, evaluated=len(items), reused=reused, results=items
    )
