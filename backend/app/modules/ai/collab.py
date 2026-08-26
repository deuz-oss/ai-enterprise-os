"""Fase 12 — AI Kolaborasi (PRD §9.6, gelombang 2 chat).

1. @AEOS via DM/channel: jawaban atas pertanyaan tenant dari data lintas
   aplikasi yang sudah terverifikasi (pola sama dengan tanya-laporan
   akuntansi) + saran routing ke tim yang tepat bila tidak bisa menjawab.
2. Rangkuman thread panjang menjadi poin keputusan/tugas.
3. Digest harian: item penting deterministik (approval menunggu, SLA,
   kontrak berakhir, invoice overdue).

Prinsip: konteks dikumpulkan deterministik per scope user; LLM hanya
lapisan bahasa. Tanpa AI_BASE_URL semua fitur tetap berfungsi dengan
jawaban template + routing.
"""

import logging
import secrets
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.llm import ai_configured, chat_completion
from app.modules.clients.models import Client
from app.modules.ess.models import LeaveRequest, LeaveStatus
from app.modules.finance.models import Invoice, InvoiceStatus, PaymentRequest, PaymentRequestStatus
from app.modules.hrd.models import Employee, EmploymentContract
from app.modules.payroll.models import PayrollRun, PayrollRunStatus
from app.modules.presales.models import Lead
from app.modules.recruitment.models import Candidate, JobOrder, JobOrderStatus

logger = logging.getLogger(__name__)

# Pemetaan kata kunci → tim penanggung jawab (routing §9.6 poin 5).
_TEAM_ROUTES: list[tuple[tuple[str, ...], str, str]] = [
    (("invoice", "tagihan", "pajak", "ppn", "pph", "bayar", "kas", "bank"), "finance", "Finance"),
    (
        ("gaji", "payrol", "payroll", "saltab", "bpjs"),
        "hr_operations",
        "HR (internal) / Operations (proyek)",
    ),
    (("cuti", "izin", "kontrak", "karyawan", "absensi"), "hr", "HR"),
    (("kandidat", "rekrut", "job order", "jo ", "placement"), "recruiter", "Recruiter"),
    (("lead", "pipeline", "prospek", "penawaran"), "business_dev", "Business Dev"),
]


def route_suggestion(question: str) -> dict | None:
    q = question.lower()
    for keywords, team, label in _TEAM_ROUTES:
        if any(k in q for k in keywords):
            return {"team": team, "team_label": label}
    return None


def ensure_aeos_user(db: Session, tenant_id):
    """Identitas bot AEOS per tenant (tanpa password aktif; tak bisa login).

    Email acak-stabil agar unik global; dicari ulang lewat pola email +
    nama tampilan 'AEOS'.
    """
    from app.modules.auth.models import User, UserRole

    existing = (
        db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.full_name == "AEOS",
                User.email.like("aeos.%@aeos.internal"),
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing
    suffix = secrets.token_hex(6)
    user = User(
        tenant_id=tenant_id,
        email=f"aeos.{suffix}@aeos.internal",
        full_name="AEOS",
        hashed_password=secrets.token_urlsafe(32),
        role=UserRole.management,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _ai_license_active(db: Session, tenant_id) -> bool:
    from app.modules.platform.models import LicenseStatus, TenantAppLicense

    lic = (
        db.execute(
            select(TenantAppLicense).where(
                TenantAppLicense.tenant_id == tenant_id,
                TenantAppLicense.app_key == "ai_addon",
                TenantAppLicense.status.in_([LicenseStatus.active, LicenseStatus.trial]),
            )
        )
        .scalars()
        .first()
    )
    if lic is None:
        return False
    if lic.expires_at is not None and lic.expires_at < datetime.now(UTC):
        return False
    return True


# ---------- Konteks lintas aplikasi (deterministik, per scope) ----------


def _staff_context(db: Session) -> list[str]:
    today = date.today()
    parts: list[str] = []

    leads = db.execute(select(func.count(Lead.id))).scalar() or 0
    parts.append(f"Total lead tercatat: {leads}")

    open_jo = (
        db.execute(
            select(JobOrder).where(
                JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.screening])
            )
        )
        .scalars()
        .all()
    )
    parts.append(f"Job order aktif (open/screening): {len(open_jo)}")
    for jo in open_jo[:3]:
        due = f", jatuh tempo {jo.due_date.isoformat()}" if jo.due_date else ""
        client = jo.client.name if jo.client else "-"
        parts.append(f"  - {jo.title} @ {client} ({jo.status.value}{due})")

    candidates = db.execute(
        select(Candidate.status, func.count(Candidate.id)).group_by(Candidate.status)
    ).all()
    if candidates:
        breakdown = ", ".join(f"{s.value}: {c}" for s, c in candidates)
        parts.append(f"Kandidat per status — {breakdown}")

    employees = (
        db.execute(select(func.count(Employee.id)).where(Employee.user_id.is_not(None))).scalar()
        or 0
    )
    total_emp = db.execute(select(func.count(Employee.id))).scalar() or 0
    parts.append(f"Karyawan: {total_emp} total, {employees} punya akun portal")

    ending = today + timedelta(days=30)
    contracts = (
        db.execute(
            select(func.count(EmploymentContract.id)).where(
                EmploymentContract.end_date.is_not(None),
                EmploymentContract.end_date <= ending,
                EmploymentContract.end_date >= today,
            )
        ).scalar()
        or 0
    )
    if contracts:
        parts.append(f"Kontrak berakhir dalam 30 hari: {contracts}")

    waiting_prs = (
        db.execute(
            select(PaymentRequest).where(
                PaymentRequest.status == PaymentRequestStatus.waiting_superior
            )
        )
        .scalars()
        .all()
    )
    if waiting_prs:
        total = sum(float(p.amount) for p in waiting_prs)
        parts.append(
            f"Payment Request menunggu approval: {len(waiting_prs)} senilai Rp{total:,.0f}"
        )

    outstanding = (
        db.execute(
            select(Invoice).where(Invoice.status.in_([InvoiceStatus.draft, InvoiceStatus.sent]))
        )
        .scalars()
        .all()
    )
    overdue = [i for i in outstanding if i.due_date and i.due_date < today]
    if outstanding:
        parts.append(
            f"Invoice belum lunas: {len(outstanding)} (overdue {len(overdue)}, "
            f"total tertagih Rp{sum(float(i.total_due) for i in outstanding):,.0f})"
        )

    runs = (
        db.execute(
            select(PayrollRun).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).limit(2)
        )
        .scalars()
        .all()
    )
    for r in runs:
        parts.append(f"Payrol terakhir {r.month}/{r.year}: {r.status.value}")

    from app.modules.accounting.service import income_statement

    income = income_statement(db, year=today.year)
    parts.append(
        f"Laba rugi {today.year}: pendapatan Rp{income.total_revenue:,.0f}, "
        f"laba bersih Rp{income.net_income:,.0f}"
    )
    return parts


def _employee_context(db: Session, user) -> list[str]:
    from app.modules.ess.service import get_own_employee, get_own_leave_balance, list_own_attendance

    employee = get_own_employee(db, user)
    parts = [f"Anda tercatat sebagai karyawan: {employee.full_name}"]
    today = date.today()

    balance = get_own_leave_balance(db, user, today.year)
    if balance is not None:
        parts.append(f"Sisa cuti tahunan: {balance.total_days - balance.used_days} hari")
    else:
        parts.append("Jatah cuti tahunan belum diatur HR")

    summaries = list_own_attendance(db, user, year=today.year, month=today.month)
    hadir = sum(s.present_days for s in summaries)
    lembur = sum(s.overtime_hours for s in summaries)
    parts.append(f"Rekap bulan ini: {hadir} hari hadir, {lembur} jam lembur")

    pending_leaves = [
        lr
        for lr in db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status == LeaveStatus.pending,
            )
        )
    ]
    if pending_leaves:
        parts.append(f"Pengajuan cuti/izin menunggu: {len(pending_leaves)}")
    latest_payslip_note = "slip gaji terbaru dapat dilihat di Portal Saya"
    parts.append(latest_payslip_note)
    return parts


# ---------- @AEOS: jawab pertanyaan ----------


def answer_question(db: Session, user, question: str) -> dict:
    """Jawaban @AEOS dari data lintas aplikasi + routing bila di luar cakupan."""
    question = (question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Pertanyaan kosong")

    is_worker = getattr(user.role, "value", user.role) == "karyawan"
    context_parts = _employee_context(db, user) if is_worker else _staff_context(db)
    route = route_suggestion(question)

    context_text = "\n".join(context_parts)
    answer = _narrate(question, context_text, is_worker)

    sources = (
        ["portal_saya"]
        if is_worker
        else ["presales", "recruitment", "hrd", "payroll", "finance", "accounting"]
    )
    return {
        "question": question,
        "answer": answer,
        "route_to": route,
        "sources": sources,
        "llm": ai_configured(),
    }


def _narrate(question: str, context: str, is_worker: bool) -> str:
    system = (
        "Anda adalah AEOS, asisten operasional perusahaan outsourcing Indonesia. "
        "Jawab pertanyaan pengguna dalam Bahasa Indonesia secara ringkas HANYA "
        "memakai data berikut. Bila datanya tidak menjawab pertanyaan, katakan "
        "jujur dan sarankan tim yang sesuai. Jangan mengarang angka."
    )
    try:
        reply = chat_completion(
            system, f"DATA:\n{context}\n\nPERTANYAAN: {question}", json_mode=False
        )
        return str(reply).strip()[:2000]
    except Exception:  # noqa: BLE001 - fallback tanpa LLM
        pass
    header = (
        "Berikut data yang relevan dari sistem:" if not is_worker else "Berikut data portal Anda:"
    )
    route = route_suggestion(question)
    tail = ""
    if route:
        tail = (
            f"\n\nUntuk hal ini saya sarankan menghubungi tim {route['team_label']} "
            "(gunakan mention atau DM)."
        )
    trimmed = "\n".join(context.splitlines()[:12])
    return f"{header}\n{trimmed}{tail}"


# ---------- Rangkuman thread ----------


def summarize_messages(db: Session, user, contents: list[str]) -> dict:
    """Rangkum daftar isi pesan thread menjadi poin keputusan/tugas."""
    joined = "\n".join(f"- {c[:400]}" for c in contents)[:12000]
    system = (
        "Anda merangkum diskusi kerja tim dalam Bahasa Indonesia. Keluarkan "
        "maksimal 5 poin berformat '- ...' yang memuat KEPUTUSAN dan TUGAS "
        "beserta pemiliknya bila disebut. Abaikan basa-basi."
    )
    try:
        summary = chat_completion(system, f"PESAN THREAD:\n{joined}", json_mode=False)
        summary = str(summary).strip()[:2000]
        llm = True
    except Exception:  # noqa: BLE001
        participants_hint = f"{len(contents)} pesan dibahas"
        first = contents[0][:200] if contents else ""
        last = contents[-1][:200] if contents else ""
        summary = (
            f"Ringkasan deterministik ({participants_hint}):\n"
            f"- Awal diskusi: {first}\n- Pesan terakhir: {last}"
        )
        llm = False
    return {"summary": summary, "message_count": len(contents), "llm": llm}


# ---------- Digest harian (deterministik) ----------


def daily_digest(db: Session, user) -> dict:
    today = date.today()
    items: list[dict] = []
    is_worker = getattr(user.role, "value", user.role) == "karyawan"

    if not is_worker:
        waiting = (
            db.execute(
                select(PaymentRequest).where(
                    PaymentRequest.status == PaymentRequestStatus.waiting_superior
                )
            )
            .scalars()
            .all()
        )
        if waiting:
            items.append(
                {
                    "type": "approval_menunggu",
                    "detail": f"{len(waiting)} Payment Request menunggu approval",
                    "refs": [p.pr_number for p in waiting[:5]],
                }
            )
        submitted_runs = (
            db.execute(
                select(PayrollRun).where(PayrollRun.status == PayrollRunStatus.submitted_to_client)
            )
            .scalars()
            .all()
        )
        if submitted_runs:
            items.append(
                {
                    "type": "payroll_klien",
                    "detail": f"{len(submitted_runs)} payrol proyek menunggu persetujuan klien",
                    "refs": [f"{r.month}/{r.year}" for r in submitted_runs[:5]],
                }
            )
        soon = today + timedelta(days=7)
        jo_due = (
            db.execute(
                select(JobOrder).where(
                    JobOrder.due_date.is_not(None),
                    JobOrder.due_date >= today,
                    JobOrder.due_date <= soon,
                    JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.screening]),
                )
            )
            .scalars()
            .all()
        )
        if jo_due:
            items.append(
                {
                    "type": "sla_job_order",
                    "detail": f"{len(jo_due)} job order jatuh tempo ≤7 hari",
                    "refs": [j.title for j in jo_due[:5]],
                }
            )
        contracts = (
            db.execute(
                select(func.count(EmploymentContract.id)).where(
                    EmploymentContract.end_date.is_not(None),
                    EmploymentContract.end_date >= today,
                    EmploymentContract.end_date <= today + timedelta(days=14),
                )
            ).scalar()
            or 0
        )
        if contracts:
            items.append(
                {
                    "type": "kontrak_berakhir",
                    "detail": f"{contracts} kontrak berakhir ≤14 hari",
                    "refs": [],
                }
            )
        invoices = (
            db.execute(select(Invoice).where(Invoice.status == InvoiceStatus.sent)).scalars().all()
        )
        overdue = [i for i in invoices if i.due_date and i.due_date < today]
        if overdue:
            items.append(
                {
                    "type": "invoice_overdue",
                    "detail": f"{len(overdue)} invoice melewati jatuh tempo "
                    f"(Rp{sum(float(i.total_due) for i in overdue):,.0f})",
                    "refs": [i.invoice_no for i in overdue[:5]],
                }
            )
        clients = db.execute(select(func.count(Client.id))).scalar() or 0
        leads = db.execute(select(func.count(Lead.id))).scalar() or 0
        items.append(
            {
                "type": "ringkasan",
                "detail": f"{clients} klien aktif · {leads} lead tercatat",
                "refs": [],
            }
        )
    else:
        from app.modules.ess.service import get_own_employee

        employee = get_own_employee(db, user)
        pending = db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status == LeaveStatus.pending,
            )
        ).all()
        if pending:
            items.append(
                {
                    "type": "cuti_menunggu",
                    "detail": f"{len(pending)} pengajuan cuti/izin Anda menunggu keputusan",
                    "refs": [],
                }
            )
        items.append(
            {
                "type": "pengingat",
                "detail": "Jangan lupa clock-in/out via aplikasi mobile (GPS + selfie)",
                "refs": [],
            }
        )

    return {"date": today.isoformat(), "items": items}
