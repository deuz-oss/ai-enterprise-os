"""Rekonsiliasi invoice ↔ absensi (audit 2026-10-08, item "still open").

Invoice outsourcing ditagih dari slip payroll karyawan klien. Sebelum invoice
dikirim, staf finance perlu tahu apakah yang DITAGIH (slip: headcount, jam
lembur, bruto) cocok dengan absensi yang DISETUJUI klien. Semua temuan dihitung
deterministik dari data; AI (bila dikonfigurasi) hanya merangkum temuan yang
sama -- tidak pernah menjadi sumber angka dan tidak mengubah apa pun.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm import ai_configured, chat_completion
from app.core.money import format_rupiah, to_decimal
from app.modules.finance.models import Invoice
from app.modules.finance.service import (
    _get_invoice,
    billed_by_components,
    payroll_total_for_run,
    select_billing_run,
)
from app.modules.hrd.models import Employee
from app.modules.payroll.models import (
    AttendanceSummary,
    PayrollRun,
    PayrollRunStatus,
    Payslip,
)
from app.modules.recruitment.models import JobOrder, Placement

MAX_FINDINGS = 50
# Selisih payroll_total invoice vs total slip saat ini yang masih dianggap
# pembulatan (rupiah).
TOTAL_TOLERANCE = Decimal("1")


def _pick_run(db: Session, invoice: Invoice) -> PayrollRun | None:
    """Run sumber tagihan: yang tersimpan di invoice bila ada.

    Invoice lama (sebelum kolom payroll_run_id) dipilih ulang: run proyek
    milik klien dulu -- jalur invoice otomatis saat klien menyetujui payrol
    proyek -- lalu aturan yang sama dengan generate invoice tanpa run_id.
    """
    if invoice.payroll_run_id is not None:
        return db.get(PayrollRun, invoice.payroll_run_id)
    own = [
        r
        for r in db.execute(
            select(PayrollRun).where(
                PayrollRun.year == invoice.year,
                PayrollRun.month == invoice.month,
                PayrollRun.client_id == invoice.client_id,
            )
        ).scalars()
    ]
    if own:
        finals = [r for r in own if r.status == PayrollRunStatus.final]
        return max(finals or own, key=lambda r: str(r.created_at or ""))
    return select_billing_run(db, invoice.client_id, invoice.year, invoice.month)


def _client_employee_ids(db: Session, client_id: UUID) -> set[UUID]:
    return set(
        db.execute(
            select(Employee.id)
            .join(Placement, Employee.placement_id == Placement.id)
            .join(JobOrder, Placement.job_order_id == JobOrder.id)
            .where(JobOrder.client_id == client_id)
        ).scalars()
    )


def reconcile_invoice(db: Session, invoice_id: str) -> dict:
    invoice = _get_invoice(db, invoice_id)
    run = _pick_run(db, invoice)
    project_run = run is not None and billed_by_components(run)

    # Run proyek sudah khusus klien ini; run umum disaring lewat placement.
    client_emps: set[UUID] = set() if project_run else _client_employee_ids(db, invoice.client_id)
    slips: list[Payslip] = []
    if run is not None:
        slips = list(db.execute(select(Payslip).where(Payslip.run_id == run.id)).scalars())
        if not project_run:
            slips = [s for s in slips if s.employee_id in client_emps]
    slip_emp_ids = {s.employee_id for s in slips}

    # Absensi periode: karyawan yang ditagih + karyawan klien lain yang punya
    # rekap (supaya absensi disetujui tanpa slip ikut terlihat).
    scope = slip_emp_ids | client_emps
    summaries = (
        list(
            db.execute(
                select(AttendanceSummary).where(
                    AttendanceSummary.year == invoice.year,
                    AttendanceSummary.month == invoice.month,
                    AttendanceSummary.employee_id.in_(scope),
                )
            ).scalars()
        )
        if scope
        else []
    )
    att_by_emp = {a.employee_id: a for a in summaries}

    findings: list[dict] = []

    def add(severity: str, kind: str, message: str, emp_id: UUID | None, name: str | None):
        findings.append(
            {
                "severity": severity,
                "kind": kind,
                "employee_id": str(emp_id) if emp_id else None,
                "employee_name": name,
                "message": message,
            }
        )

    def emp_name(emp: Employee | None, emp_id: UUID) -> str:
        return emp.full_name if emp is not None else str(emp_id)

    if run is None:
        add(
            "high",
            "tanpa_payroll",
            f"Tidak ada run payroll periode {invoice.month}/{invoice.year} -- "
            "invoice tidak bisa dicocokkan dengan slip.",
            None,
            None,
        )

    for slip in slips:
        name = emp_name(slip.employee, slip.employee_id)
        att = att_by_emp.get(slip.employee_id)
        if att is None:
            add(
                "high",
                "tanpa_absensi",
                "Ditagih, tetapi tidak ada rekap absensi.",
                slip.employee_id,
                name,
            )
            continue
        if not att.client_approved:
            add(
                "high",
                "absensi_belum_disetujui",
                "Ditagih, tetapi rekap absensi belum disetujui klien.",
                slip.employee_id,
                name,
            )
        if att.present_days == 0:
            add("medium", "hadir_nol", "Ditagih dengan 0 hari hadir.", slip.employee_id, name)
        if slip.overtime_hours != att.overtime_hours:
            add(
                "medium",
                "lembur_beda",
                f"Lembur ditagih {slip.overtime_hours} jam, absensi {att.overtime_hours} jam.",
                slip.employee_id,
                name,
            )
    for att in summaries:
        if att.client_approved and att.employee_id not in slip_emp_ids and run is not None:
            add(
                "medium",
                "absensi_tidak_ditagih",
                f"Absensi disetujui ({att.present_days} hari) tetapi tidak ada slip -- "
                "belum ditagih.",
                att.employee_id,
                emp_name(att.employee, att.employee_id),
            )

    # Total payroll di invoice vs total slip saat ini (slip berubah setelah
    # invoice dibuat, mis. run digenerate ulang).
    current_total: Decimal | None = None
    if run is not None and slips:
        current_total = to_decimal(payroll_total_for_run(db, run, invoice.client_id))
        billed = to_decimal(invoice.payroll_total)
        if abs(billed - current_total) > TOTAL_TOLERANCE:
            add(
                "high",
                "total_beda",
                f"Payroll di invoice {format_rupiah(billed)}, total slip saat ini "
                f"{format_rupiah(current_total)}.",
                None,
                None,
            )

    order = {"high": 0, "medium": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["employee_name"] or ""))

    approved = [a for a in summaries if a.client_approved and a.employee_id in slip_emp_ids]
    result = {
        "invoice_id": str(invoice.id),
        "invoice_no": invoice.invoice_no,
        "period": f"{invoice.month}/{invoice.year}",
        "run_id": str(run.id) if run else None,
        "run_status": run.status.value if run else None,
        "totals": {
            "headcount_billed": len(slips),
            "headcount_approved": len(approved),
            "overtime_billed": sum(s.overtime_hours for s in slips),
            "overtime_approved": sum(a.overtime_hours for a in approved),
            "payroll_billed": float(to_decimal(invoice.payroll_total)),
            "payroll_current": float(current_total) if current_total is not None else None,
        },
        "findings": findings[:MAX_FINDINGS],
        "findings_total": len(findings),
        "summary": None,
        "summary_source": "none",
    }
    if ai_configured() and findings:
        summary = _try_ai_summary(result)
        if summary:
            result["summary"] = summary
            result["summary_source"] = "ai"
    return result


def _try_ai_summary(rec: dict) -> str | None:
    """Ringkas temuan yang SUDAH dihitung; gagal apa pun -> tanpa ringkasan."""
    lines = [f"Invoice {rec['invoice_no']} periode {rec['period']}"]
    for key, value in rec["totals"].items():
        lines.append(f"{key}: {value}")
    for f in rec["findings"][:20]:
        lines.append(f"[{f['severity']}] {f['employee_name'] or '-'}: {f['message']}")
    try:
        text = chat_completion(
            "Anda membantu staf finance perusahaan outsourcing Indonesia memeriksa "
            "invoice terhadap absensi yang disetujui klien. Ringkas temuan berikut "
            "dalam 2-3 kalimat Bahasa Indonesia: apa yang perlu dibereskan sebelum "
            "invoice dikirim. Hanya gunakan angka & nama dari data; jangan menebak "
            "penyebab yang tidak tertulis.",
            "\n".join(lines),
            json_mode=False,
            feature="finance.invoice_attendance_reconciliation",
        )
        return str(text).strip()[:1200] or None
    except Exception:  # noqa: BLE001 - ringkasan AI opsional
        return None
