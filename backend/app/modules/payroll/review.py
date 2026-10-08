"""Tinjauan run payroll sebelum finalisasi (audit 2026-10-08 Phase 6).

Finalisasi tidak bisa dibatalkan dan memposting jurnal, jadi sebelum user
mengetik konfirmasi kita tunjukkan apa yang BERUBAH dibanding run final
sebelumnya. Semua temuan dihitung deterministik dari data slip; AI (bila
dikonfigurasi) hanya merangkum temuan itu menjadi satu paragraf -- AI tidak
pernah menjadi sumber angka dan tidak mengubah apa pun.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm import ai_configured, chat_completion
from app.core.money import ZERO, format_rupiah, to_decimal
from app.modules.payroll.models import PayrollRun, PayrollRunStatus, Payslip

# Ambang "perubahan besar" per karyawan dibanding run sebelumnya.
NET_CHANGE_RATIO = Decimal("0.20")
TAX_CHANGE_RATIO = Decimal("0.50")
MAX_FINDINGS = 50


def _previous_final_run(db: Session, run: PayrollRun) -> PayrollRun | None:
    """Run FINAL terakhir sebelum periode ini, jenis (dan klien) yang sama."""
    period = run.year * 12 + run.month
    stmt = select(PayrollRun).where(
        PayrollRun.status == PayrollRunStatus.final,
        PayrollRun.run_type == run.run_type,
        PayrollRun.id != run.id,
    )
    if run.client_id is not None:
        stmt = stmt.where(PayrollRun.client_id == run.client_id)
    candidates = [r for r in db.execute(stmt).scalars() if r.year * 12 + r.month < period]
    return max(candidates, key=lambda r: r.year * 12 + r.month, default=None)


def _slips(db: Session, run_id: UUID) -> list[Payslip]:
    return list(db.execute(select(Payslip).where(Payslip.run_id == run_id)).scalars())


def _ratio(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous)


def _name(slip: Payslip) -> str:
    return slip.employee.full_name if slip.employee is not None else str(slip.employee_id)


def review_run(db: Session, run: PayrollRun) -> dict:
    current = _slips(db, run.id)
    previous_run = _previous_final_run(db, run)
    previous = _slips(db, previous_run.id) if previous_run else []
    prev_by_emp = {s.employee_id: s for s in previous}
    cur_ids = {s.employee_id for s in current}

    findings: list[dict] = []

    def add(severity: str, kind: str, message: str, slip: Payslip | None = None) -> None:
        findings.append(
            {
                "severity": severity,
                "kind": kind,
                "employee_id": str(slip.employee_id) if slip else None,
                "employee_name": _name(slip) if slip else None,
                "message": message,
            }
        )

    for slip in current:
        net = to_decimal(slip.net_pay)
        gross = to_decimal(slip.gross)
        if net < 0:
            add("high", "net_negatif", f"Net pay negatif ({format_rupiah(net)}).", slip)
        if gross == 0:
            add("high", "bruto_nol", "Bruto Rp0 -- cek gaji pokok/absensi.", slip)
        prev = prev_by_emp.get(slip.employee_id)
        if prev is None:
            if previous_run is not None:
                add("info", "karyawan_baru", "Tidak ada di run final sebelumnya.", slip)
            continue
        net_ratio = _ratio(net, to_decimal(prev.net_pay))
        if net_ratio is not None and abs(net_ratio) >= NET_CHANGE_RATIO:
            add(
                "medium",
                "net_berubah",
                f"Net pay {format_rupiah(prev.net_pay)} → {format_rupiah(net)} "
                f"({net_ratio * 100:+.0f}%).",
                slip,
            )
        tax_ratio = _ratio(to_decimal(slip.tax_pph21), to_decimal(prev.tax_pph21))
        if tax_ratio is not None and tax_ratio >= TAX_CHANGE_RATIO:
            add(
                "medium",
                "pph21_naik",
                f"PPh21 {format_rupiah(prev.tax_pph21)} → {format_rupiah(slip.tax_pph21)} "
                f"({tax_ratio * 100:+.0f}%).",
                slip,
            )
    for prev in previous:
        if prev.employee_id not in cur_ids:
            add(
                "medium",
                "karyawan_hilang",
                "Ada di run final sebelumnya, tidak ada di run ini.",
                prev,
            )

    order = {"high": 0, "medium": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["employee_name"] or ""))

    def total(slips: list[Payslip], attr: str) -> Decimal:
        return sum((to_decimal(getattr(s, attr)) for s in slips), ZERO)

    totals = {
        key: {
            "current": float(total(current, attr)),
            "previous": float(total(previous, attr)) if previous_run else None,
        }
        for key, attr in (("gross", "gross"), ("net", "net_pay"), ("pph21", "tax_pph21"))
    }
    totals["slips"] = {
        "current": len(current),
        "previous": len(previous) if previous_run else None,
    }

    result = {
        "run_id": str(run.id),
        "period": f"{run.month}/{run.year}",
        "compared_to": (
            {"run_id": str(previous_run.id), "period": f"{previous_run.month}/{previous_run.year}"}
            if previous_run
            else None
        ),
        "totals": totals,
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


def _try_ai_summary(review: dict) -> str | None:
    """Ringkas temuan yang SUDAH dihitung; gagal apa pun -> tanpa ringkasan."""
    lines = [f"Periode {review['period']}"]
    if review["compared_to"]:
        lines.append(f"Dibanding run final {review['compared_to']['period']}")
    for key, value in review["totals"].items():
        lines.append(f"{key}: sekarang {value['current']}, sebelumnya {value['previous']}")
    for f in review["findings"][:20]:
        lines.append(f"[{f['severity']}] {f['employee_name'] or '-'}: {f['message']}")
    try:
        text = chat_completion(
            "Anda membantu staf payroll perusahaan outsourcing Indonesia meninjau "
            "run payroll sebelum difinalisasi. Ringkas temuan berikut dalam 2-3 "
            "kalimat Bahasa Indonesia: apa yang paling perlu dicek sebelum "
            "finalisasi. Hanya gunakan angka & nama dari data; jangan menebak "
            "penyebab yang tidak tertulis.",
            "\n".join(lines),
            json_mode=False,
            feature="payroll.pre_finalize_review",
        )
        return str(text).strip()[:1200] or None
    except Exception:  # noqa: BLE001 - ringkasan AI opsional
        return None
