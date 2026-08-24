"""Rekap iuran BPJS bulanan + ekspor data siap unggah ke portal BPJS.

BPJS belum menyediakan API publik self-service untuk employer, sehingga
v1 menghasilkan perhitungan dan file ekspor; struktur service siap
ditambahkan adapter API resmi bila kelak tersedia.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bpjs.engine import BpjsBreakdown, compute_contribution
from app.modules.bpjs.schemas import BpjsRecapOut, ContributionRowOut, RecapSummaryOut
from app.modules.hrd.models import Employee, EmployeeStatus


def _get_employees(db: Session) -> list[Employee]:
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.status == EmployeeStatus.active)
            .order_by(Employee.full_name)
        ).all()
    )


def _validate_period(year: int, month: int) -> None:
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="Bulan harus 1–12")
    if not 2000 <= year <= date.today().year + 1:
        raise HTTPException(status_code=422, detail="Tahun tidak wajar")


def monthly_recap(db: Session, year: int, month: int) -> BpjsRecapOut:
    """Rekap iuran semua karyawan aktif untuk periode tertentu."""
    _validate_period(year, month)
    rows: list[ContributionRowOut] = []
    for emp in _get_employees(db):
        breakdown = compute_contribution(float(emp.base_salary), emp.jkk_risk_category)
        rows.append(_to_row(emp, breakdown))

    summary = RecapSummaryOut(
        employer_total=sum(r.employer_total for r in rows),
        employee_total=sum(r.employee_total for r in rows),
        grand_total=sum(r.grand_total for r in rows),
    )
    return BpjsRecapOut(year=year, month=month, rows=rows, summary=summary)


def contributions_csv(db: Session, year: int, month: int) -> tuple[str, str]:
    """CSV rekap iuran siap diunggah/diarsipkan."""
    recap = monthly_recap(db, year, month)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "No",
            "Nama Karyawan",
            "NIK",
            "No BPJS Kesehatan",
            "No BPJS TK",
            "Gaji Dasar Kesehatan",
            "Iuran Kesehatan (Perusahaan)",
            "Iuran Kesehatan (Karyawan)",
            "JKK",
            "JKM",
            "JHT (Perusahaan)",
            "JHT (Karyawan)",
            "JP (Perusahaan)",
            "JP (Karyawan)",
            "Total Perusahaan",
            "Total Karyawan",
            "Grand Total",
        ]
    )
    for idx, r in enumerate(recap.rows, start=1):
        writer.writerow(
            [
                idx,
                r.full_name,
                r.ktp_no or "",
                r.bpjs_kesehatan_no or "",
                r.bpjs_ketenagakerjaan_no or "",
                r.salary_kesehatan,
                r.breakdown["kes_employer"],
                r.breakdown["kes_employee"],
                r.breakdown["jkk"],
                r.breakdown["jkm"],
                r.breakdown["jht_employer"],
                r.breakdown["jht_employee"],
                r.breakdown["jp_employer"],
                r.breakdown["jp_employee"],
                r.employer_total,
                r.employee_total,
                r.grand_total,
            ]
        )
    writer.writerow([])
    writer.writerow(["TOTAL", "", "", "", "", "", "", "", "", "", "", "", "", "",
                     recap.summary.employer_total, recap.summary.employee_total,
                     recap.summary.grand_total])
    filename = f"bpjs-iuran-{year}{month:02d}.csv"
    return buffer.getvalue(), filename


def enrollments_csv(db: Session) -> tuple[str, str]:
    """CSV data karyawan aktif untuk pendaftaran peserta baru."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "No",
            "No Induk Karyawan",
            "Nama Lengkap",
            "NIK (KTP)",
            "Tanggal Masuk",
            "Telepon",
            "Alamat",
            "Gaji Pokok",
            "Kelas Risiko JKK",
            "No BPJS Kesehatan (bila ada)",
            "No BPJS TK (bila ada)",
        ]
    )
    for idx, emp in enumerate(_get_employees(db), start=1):
        writer.writerow(
            [
                idx,
                emp.employee_no,
                emp.full_name,
                emp.ktp_no or "",
                emp.join_date or "",
                emp.phone or "",
                emp.address or "",
                float(emp.base_salary),
                emp.jkk_risk_category or "default",
                emp.bpjs_kesehatan_no or "",
                emp.bpjs_ketenagakerjaan_no or "",
            ]
        )
    filename = f"bpjs-peserta-{date.today().isoformat()}.csv"
    return buffer.getvalue(), filename


def _to_row(emp: Employee, b: BpjsBreakdown) -> ContributionRowOut:
    return ContributionRowOut(
        employee_id=emp.id,
        full_name=emp.full_name,
        ktp_no=emp.ktp_no,
        bpjs_kesehatan_no=emp.bpjs_kesehatan_no,
        bpjs_ketenagakerjaan_no=emp.bpjs_ketenagakerjaan_no,
        salary_kesehatan=b.salary_kesehatan,
        salary_jp=b.salary_jp,
        breakdown={
            "kes_employer": b.kes_employer,
            "kes_employee": b.kes_employee,
            "jkk": b.jkk,
            "jkm": b.jkm,
            "jht_employer": b.jht_employer,
            "jht_employee": b.jht_employee,
            "jp_employer": b.jp_employer,
            "jp_employee": b.jp_employee,
        },
        employer_total=b.employer_total,
        employee_total=b.employee_total,
        grand_total=b.grand_total,
    )
