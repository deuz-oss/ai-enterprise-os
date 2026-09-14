"""Bersihkan semua data yang dibuat `seed_dummy_attendance.py`.

Tulis DB langsung (bukan lewat HTTP) karena dua alasan:
- Tidak ada endpoint DELETE utk `AttendanceRecord`/`AttendanceSummary` sama
  sekali di API (absensi memang didesain append/upsert-only, lihat
  `attendance/router.py`).
- `DELETE /employees/{id}` menolak (422) selama masih ada baris lain yang
  mereferensikannya (`assert_not_referenced`) -- termasuk record & rekap
  absensi yang baru dibuat -- jadi baris itu harus dibersihkan dulu.

Sebelum menghapus apa pun, script ini SELALU cek `referencing_row_counts`
dulu (helper yang sama dipakai endpoint delete asli) -- kalau ternyata ada
baris LAIN yang menautkan ke karyawan/akun dummy ini (mis. Anda pernah
mengajukan cuti/koreksi lewat portal pakai akun dummy-karyawan), dia
BERHENTI dan melaporkan alih-alih menghapus paksa/cascade.

Hanya menyentuh baris yang cocok employee_no DUMMY-001/DUMMY-002 atau email
di daftar akun dummy -- tidak pernah menyentuh data lain.

Pakai: .venv/Scripts/python scripts/unseed_dummy_attendance.py
"""

from __future__ import annotations

import app.main  # noqa: F401 -- registrasi semua model (FK lintas modul butuh ini)
from app.core.database import SessionLocal, referencing_row_counts
from app.modules.auth.models import User
from app.modules.hrd.models import Employee

DUMMY_EMPLOYEE_NOS = ["DUMMY-001", "DUMMY-002"]
DUMMY_EMAILS = [
    "dummy-seed-admin@outsourcing.co.id",
    "dummy-hr@outsourcing.co.id",
    "dummy-ops@outsourcing.co.id",
    "dummy-mgmt@outsourcing.co.id",
    "dummy-recruiter@outsourcing.co.id",
    "dummy-karyawan@outsourcing.co.id",
]


def main() -> int:
    db = SessionLocal()
    try:
        employees = db.query(Employee).filter(Employee.employee_no.in_(DUMMY_EMPLOYEE_NOS)).all()
        for emp in employees:
            from app.modules.attendance.models import AttendanceRecord
            from app.modules.payroll.models import AttendanceSummary

            n_records = (
                db.query(AttendanceRecord)
                .filter(AttendanceRecord.employee_id == emp.id)
                .delete(synchronize_session=False)
            )
            n_summaries = (
                db.query(AttendanceSummary)
                .filter(AttendanceSummary.employee_id == emp.id)
                .delete(synchronize_session=False)
            )
            db.commit()
            print(
                f"  [-] {emp.employee_no}: {n_records} record absensi + "
                f"{n_summaries} rekap bulanan dihapus"
            )

            leftover = referencing_row_counts(db, "employees", emp.id)
            if leftover:
                print(
                    f"  [!] {emp.employee_no} masih direferensikan tabel lain "
                    f"{leftover} -- DILEWATI (bukan cuma dari seed, ada aktivitas "
                    "lain di atasnya; hapus manual dari halaman Karyawan kalau "
                    "memang mau dibuang)."
                )
                continue
            db.delete(emp)
            db.commit()
            print(f"  [-] karyawan {emp.employee_no} ({emp.full_name}) dihapus")

        for email in DUMMY_EMAILS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                continue
            leftover = referencing_row_counts(db, "users", user.id)
            if leftover:
                print(
                    f"  [!] akun {email} masih direferensikan tabel lain {leftover} "
                    "-- DILEWATI (nonaktifkan manual lewat halaman Pengguna kalau perlu)."
                )
                continue
            db.delete(user)
            db.commit()
            print(f"  [-] akun {email} dihapus")

        print("\nSelesai membersihkan data dummy.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
