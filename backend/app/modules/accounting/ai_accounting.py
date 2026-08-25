"""AI Layer Akuntansi (PRD §8.8) — pembeda vertikal Fase 10.

Prinsip (PRD): semua jawaban berbasis data terstruktur yang dapat
diverifikasi. Fitur deterministik (close-checklist, anomali, kategori)
TIDAK memerlukan LLM; narasi eksekutif dan tanya-laporan memakai LLM
sebagai lapisan bahasa di atas angka yang sudah terverifikasi.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.llm import chat_completion
from app.modules.accounting.models import (
    JournalEntry,
    JournalEntryStatus,
    PurchaseBill,
)
from app.modules.accounting.service import get_account_by_code
from app.modules.finance.models import Invoice, InvoiceStatus, PaymentRequest, PaymentRequestStatus
from app.modules.payroll.models import PayrollRun, PayrollRunStatus

logger = logging.getLogger(__name__)

# ---------- 1. Asisten tutup buku (deterministik) ----------


def close_checklist(db: Session, year: int, month: int) -> dict:
    """Checklist otomatis sebelum tutup buku: temuan + status tiap item."""
    findings: list[dict] = []
    start = f"{year}-{str(month).zfill(2)}-01"
    end_day = _last_day(year, month)
    end = f"{year}-{str(month).zfill(2)}-{end_day:02d}"

    # 1a) Jurnal memorial belum diposting
    memorials = (
        db.execute(
            select(JournalEntry)
            .where(JournalEntry.status == JournalEntryStatus.memorial)
            .where(JournalEntry.entry_date >= start)
            .where(JournalEntry.entry_date <= end)
        )
        .scalars()
        .all()
    )
    if memorials:
        findings.append(
            {
                "code": "memorial_unposted",
                "severity": "error",
                "detail": f"{len(memorials)} jurnal memorial belum diposting",
                "items": [str(e.id) for e in memorials],
            }
        )

    # 1b) Invoice tanpa jurnal auto
    invoices_no_journal = (
        db.execute(
            select(Invoice).where(
                Invoice.year == year,
                Invoice.month == month,
                Invoice.status != InvoiceStatus.draft,
            )
        )
        .scalars()
        .all()
    )
    missing_invoice_journal = [
        inv
        for inv in invoices_no_journal
        if not _has_auto_journal(db, "invoice_issued", str(inv.id))
    ]
    if missing_invoice_journal:
        findings.append(
            {
                "code": "invoice_without_journal",
                "severity": "warning",
                "detail": f"{len(missing_invoice_journal)} invoice terkirim tanpa jurnal otomatis",
                "items": [i.invoice_no for i in missing_invoice_journal],
            }
        )

    # 1c) Payrol proyek approved tanpa jurnal
    payroll_approved = (
        db.execute(
            select(PayrollRun).where(
                PayrollRun.year == year,
                PayrollRun.month == month,
                PayrollRun.status == PayrollRunStatus.client_approved,
            )
        )
        .scalars()
        .all()
    )
    missing_payroll_journal = [
        r
        for r in payroll_approved
        if not _has_auto_journal(db, "payroll_finalized_proyek", str(r.id))
    ]
    if missing_payroll_journal:
        findings.append(
            {
                "code": "payroll_without_journal",
                "severity": "info",
                "detail": f"{len(missing_payroll_journal)} payrol disetujui klien tapi belum final",
                "items": [f"{r.month}/{r.year}" for r in missing_payroll_journal],
            }
        )

    # 1d) PR dieksekusi tanpa jurnal
    executed_prs = (
        db.execute(
            select(PaymentRequest).where(PaymentRequest.status == PaymentRequestStatus.executed)
        )
        .scalars()
        .all()
    )
    prs_this_month = [
        pr
        for pr in executed_prs
        if pr.executed_at
        and pr.executed_at.year == year
        and pr.executed_at.month == month
        and not _has_auto_journal(db, "pr_executed", str(pr.id))
    ]
    if prs_this_month:
        findings.append(
            {
                "code": "pr_without_journal",
                "severity": "warning",
                "detail": f"{len(prs_this_month)} PR dieksekusi tanpa jurnal",
                "items": [p.pr_number for p in prs_this_month],
            }
        )

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = len(findings) - errors
    ready = errors == 0

    return {
        "period": f"{year}-{str(month).zfill(2)}",
        "ready_to_close": ready,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def _has_auto_journal(db: Session, event_code: str, ref_id: str) -> bool:
    count = db.scalar(
        select(func.count(JournalEntry.id)).where(
            JournalEntry.event_code == event_code,
            JournalEntry.source_ref_type == ref_type_for(event_code),
            JournalEntry.source_ref_id == _parse(ref_id),
        )
    )
    return bool(count)


def ref_type_for(event_code: str) -> str:
    return {
        "invoice_issued": "invoice",
        "invoice_paid": "invoice",
        "payroll_finalized_internal": "payroll_run",
        "payroll_finalized_proyek": "payroll_run",
        "pr_executed": "payment_request",
    }.get(event_code, "")


def _parse(value):
    import uuid as _uuid

    try:
        return _uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _last_day(year: int, month: int) -> int:
    from calendar import monthrange

    return monthrange(year, month)[1]


# ---------- 2. Deteksi anomali & kepatuhan ----------


def detect_anomalies(db: Session, year: int, month: int) -> dict:
    """Aturan deterministik: duplikasi bill, transaksi besar, sanity PPN."""
    start = date(year, month, 1)
    end = date(year, month, _last_day(year, month))

    bills = (
        db.execute(
            select(PurchaseBill).where(
                PurchaseBill.entry_date >= start, PurchaseBill.entry_date <= end
            )
        )
        .scalars()
        .all()
    )

    anomalies: list[dict] = []

    # 2a) Duplikasi bill vendor (nama sama + nominal sama dalam rentang 7 hari)
    seen: dict[tuple[str, float], list[PurchaseBill]] = {}
    for b in bills:
        key = (b.vendor_name.lower(), round(float(b.amount)))
        seen.setdefault(key, []).append(b)
    for (vendor, amount), group in seen.items():
        if len(group) < 2:
            continue
        dates = sorted(b.entry_date for b in group)
        if (dates[-1] - dates[0]).days <= 7:
            anomalies.append(
                {
                    "type": "duplicate_bill",
                    "severity": "high",
                    "vendor": vendor,
                    "amount": amount,
                    "detail": f"{len(group)} bill dari {vendor} senilai Rp{amount:,.0f} dalam 7 hari",
                    "bill_ids": [str(b.id) for b in group],
                }
            )

    # 2b) Transaksi besar (> 3× median bulan ini)
    amounts = sorted(float(b.amount) for b in bills if float(b.amount) > 0)
    if len(amounts) >= 3:
        mid = len(amounts) // 2
        median = amounts[mid]
        threshold = median * 3
        large = [b for b in bills if float(b.amount) > threshold]
        for b in large:
            anomalies.append(
                {
                    "type": "large_transaction",
                    "severity": "medium",
                    "vendor": b.vendor_name,
                    "amount": float(b.amount),
                    "detail": (
                        f"Rp{float(b.amount):,.0f} melebihi 3× median bulan (Rp{median:,.0f})"
                    ),
                    "bill_ids": [str(b.id)],
                }
            )

    # 2c) Sanity PPN: ppn_amount harus ≈ amount × ppn_rate
    for b in bills:
        expected = round(float(b.amount) * float(b.ppn_rate))
        actual = float(b.ppn_amount)
        if abs(expected - actual) > 1:  # toleransi pembulatan Rp1
            anomalies.append(
                {
                    "type": "ppn_mismatch",
                    "severity": "medium",
                    "vendor": b.vendor_name,
                    "amount": actual,
                    "detail": f"PPN {actual:,.0f} ≠ {b.ppn_rate:.0%} × Rp{float(b.amount):,.0f}",
                    "bill_ids": [str(b.id)],
                }
            )

    high_count = sum(1 for a in anomalies if a["severity"] == "high")
    return {
        "period": f"{year}-{str(month).zfill(2)}",
        "total_anomalies": len(anomalies),
        "high_severity": high_count,
        "anomalies": anomalies,
    }


# ---------- 3. Narasi eksekutif ----------


def executive_summary(db: Session, year: int, month: int | None = None) -> dict:
    """Narasi ringkasan bulanan Bahasa Indonesia dari data terverifikasi."""
    from app.modules.accounting.service import income_statement, profit_by_client

    income = income_statement(db, year=year, month=month)
    by_client = profit_by_client(db, year=year, month=month)

    period_label = f"Bulan {month}/{year}" if month else f"Tahun {year}"
    metrics_text = (
        f"Periode: {period_label}\n"
        f"Total pendapatan: Rp{income.total_revenue:,.0f}\n"
        f"Total beban: Rp{income.total_expense:,.0f}\n"
        f"Laba bersih: Rp{income.net_income:,.0f}\n"
    )
    if by_client:
        top = max(by_client, key=lambda c: c["revenue"])
        metrics_text += f"Klien terbesar: {top['client']} (pendapatan Rp{top['revenue']:,.0f})\n"
        metrics_text += f"Jumlah klien aktif: {len(by_client)}"

    summary_text = _try_llm_narration(metrics_text, period_label)
    return {
        "period": period_label,
        "metrics": {
            "total_revenue": income.total_revenue,
            "total_expense": income.total_expense,
            "net_income": income.net_income,
            "active_clients": len(by_client),
        },
        "narrative": summary_text,
        "source": "llm"
        if "AI_BASE_URL" in str(type(summary_text)) or len(summary_text) > 100
        else "template",
    }


def _try_llm_narration(metrics_text: str, period_label: str) -> str:
    """Coba narasi via LLM; fallback ke template bila AI tidak tersedia."""
    try:
        result = chat_completion(
            "Anda adalah CFO perusahaan outsourcing Indonesia. "
            "Berdasarkan data keuangan terverifikasi berikut, tulis narasi "
            "ringkasan eksekutif 3-4 kalimat dalam Bahasa Indonesia untuk "
            "manajemen. Fokus pada pencapaian dan hal yang perlu diperhatikan. "
            "Gunakan angka dari data, jangan mengarang.",
            metrics_text,
            json_mode=False,
        )
        return str(result).strip()[:2000]
    except Exception:
        pass
    # Template fallback
    lines = metrics_text.strip().splitlines()
    revenue_line = next((ln for ln in lines if "pendapatan" in ln.lower()), "")
    net_line = next((ln for ln in lines if "laba bersih" in ln.lower()), "")
    return (
        f"Ringkasan {period_label}: {revenue_line}. {net_line}. "
        "Data lengkap tersedia di modul Akunting."
    )


# ---------- 4. Kategori bill cerdas ----------


def suggest_bill_category(db: Session, vendor_name: str, description: str | None = None) -> dict:
    """Saran COA untuk bill baru berdasarkan riwayat purchase bill serupa."""
    keyword_map = {
        "atk": ("5-9000", "Beban Operasional Lainnya"),
        "listrik": ("5-9000", "Beban Operasional Lainnya"),
        "internet": ("5-9000", "Beban Operasional Lainnya"),
        " sewa": ("5-9000", "Beban Operasional Lainnya"),
        "makan": ("5-9000", "Beban Konsumsi"),
        "transport": ("5-9000", "Beban Transportasi"),
        "laptop": ("1-2000", "Aset Tetap — Peralatan Kantor"),
        "komputer": ("1-2000", "Aset Tetap — Peralatan Kantor"),
        "software": ("1-2000", "Aset Tetap — Peralatan Kantor"),
        "iklan": ("5-4000", "Beban Rekrutmen & Penempatan"),
    }
    text = (vendor_name + " " + (description or "")).lower()
    suggestions = []
    for keyword, (code, name) in keyword_map.items():
        if keyword.strip() in text:
            acc = get_account_by_code(db, code)
            if acc is not None:
                suggestions.append(
                    {
                        "account_code": code,
                        "account_name": name,
                        "matched_keyword": keyword,
                    }
                )

    # Riwayat: cari bill dengan vendor serupa
    history = db.execute(
        select(PurchaseBill.expense_account_id, func.count(PurchaseBill.id))
        .where(PurchaseBill.vendor_name.ilike(f"%{vendor_name[:20]}%"))
        .group_by(PurchaseBill.expense_account_id)
    ).first()
    if history:
        from app.modules.accounting.models import Account

        acc = db.get(Account, history[0])
        if acc:
            suggestions.insert(
                0,
                {
                    "account_code": acc.code,
                    "account_name": acc.name,
                    "matched_keyword": "riwayat vendor",
                },
            )

    return {"vendor_name": vendor_name, "suggestions": suggestions[:3]}


# ---------- 5. Tanya laporan (structured Q&A) ----------


def ask_report(db: Session, question: str, year: int | None = None) -> dict:
    """Jawaban atas pertanyaan laporan berbasis pre-computed data.

    v1 mendukung pertanyaan tentang laba rugi, neraca saldo, laba per klien,
    arus kas. LLM digunakan untuk merangkai jawaban natural dari angka.
    """
    from app.modules.accounting.service import (
        balance_sheet,
        income_statement,
        profit_by_client,
        trial_balance,
    )

    effective_year = year or date.today().year
    q = question.lower()
    context_parts: list[str] = []

    if any(w in q for w in ("laba rugi", "pendapatan", "beban", "profit", "laba")):
        inc = income_statement(db, year=effective_year)
        context_parts.append(
            f"Laba Rugi {effective_year}: Pendapatan Rp{inc.total_revenue:,.0f}, "
            f"Beban Rp{inc.total_expense:,.0f}, Laba Bersih Rp{inc.net_income:,.0f}"
        )
        for r in inc.revenues[:3]:
            context_parts.append(f"  - {r.account_name}: Rp{r.amount:,.0f}")

    if any(w in q for w in ("neraca", "aset", "kewajiban")):
        bs = balance_sheet(db, as_of=f"{effective_year}-12-31")
        context_parts.append(
            f"Neraca {effective_year}: Aset Rp{bs.assets.total:,.0f}, "
            f"Liabilitas Rp{bs.liabilities.total:,.0f}, Ekuitas Rp{bs.equity.total:,.0f}"
        )

    if any(w in q for w in ("klien", "kontrak", "margin")):
        by_client = profit_by_client(db, year=effective_year)
        for c in by_client[:5]:
            context_parts.append(
                f"  - {c['client']}: Pendapatan Rp{c['revenue']:,.0f}, "
                f"Beban Rp{c['expense']:,.0f}, Margin Rp{c['margin']:,.0f}"
            )

    if any(w in q for w in ("neraca saldo", "saldo")):
        tb = trial_balance(db, year=effective_year)
        active = [r for r in tb if r.total_debit > 0 or r.total_credit > 0]
        context_parts.append(f"Neraca saldo {effective_year}: {len(active)} akun aktif")

    if not context_parts:
        context_parts.append(
            f"Tahun {effective_year}: gunakan kata kunci 'laba rugi', 'neraca', "
            "'klien', atau 'saldo' untuk melihat data."
        )

    context = "\n".join(context_parts)

    narrative = _try_llm_report_answer(question, context)
    return {
        "question": question,
        "year": effective_year,
        "context": context_parts,
        "answer": narrative,
    }


def _try_llm_report_answer(question: str, context: str) -> str:
    """LLM merangkai jawaban natural dari data terstruktur; fallback template."""
    try:
        result = chat_completion(
            "Anda adalah asisten keuangan perusahaan outsourcing Indonesia. "
            "Berdasarkan data terverifikasi berikut, jawab pertanyaan user "
            "dalam Bahasa Indonesia secara ringkas. Hanya gunakan angka dari "
            "data yang diberikan, jangan mengarang.",
            f"DATA:\n{context}\n\nPERTANYAAN: {question}",
            json_mode=False,
        )
        return str(result).strip()[:2000]
    except Exception:
        return context
