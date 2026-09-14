"""Bersihkan SEMUA data dummy yang dibuat skrip seed_dummy_*.py sepanjang
sesi (bukan cuma DUMMY-001/002 dari seed_dummy_attendance.py awal --
cek-gap 2026-09-14 menemukan skrip ini sudah basi begitu seed_dummy_
client_site.py & seed_dummy_placement_chain.py menambah DUMMY-003,
client/site dummy, dan beberapa candidate/job-order, plus satu employee
ad-hoc "DUMMY-TIER1-CHECK" yang dibuat manual saat verifikasi Tier 1).

Disengaja pakai POLA NAMA (prefix "DUMMY"/"dummy-", `LIKE '%(Dummy%'`),
bukan daftar tetap -- supaya tidak basi lagi tiap kali skrip seed baru
ditambah.

Tulis DB langsung (bukan lewat HTTP) karena tidak ada endpoint DELETE
untuk AttendanceRecord/AttendanceSummary sama sekali (absensi memang
didesain append/upsert-only), dan supaya urutan hapus (anak dulu baru
induk) bisa dikontrol presisi tanpa terhalang guard `assert_not_
referenced` yang dipakai endpoint DELETE asli.

Sebelum menghapus baris "induk" (employee/client/candidate/job-order),
SELALU cek `referencing_row_counts` dulu (helper yang sama dipakai
endpoint delete asli) -- kalau ternyata ada baris LAIN yang menempel yang
BUKAN bagian dari sapuan pola-nama ini, dia BERHENTI dan melaporkan alih-
alih menghapus paksa/cascade.

Pakai: .venv/Scripts/python scripts/unseed_dummy_attendance.py
"""

from __future__ import annotations

import app.main  # noqa: F401 -- registrasi semua model (FK lintas modul butuh ini)
from app.core.database import SessionLocal, referencing_row_counts
from app.modules.auth.models import User
from app.modules.hrd.models import Employee


def main() -> int:
    db = SessionLocal()
    try:
        # ---------- 1) Karyawan dummy: bersihkan anak-anaknya dulu ----------
        employees = db.query(Employee).filter(Employee.employee_no.like("DUMMY%")).all()
        for emp in employees:
            from app.modules.attendance.models import AttendanceRecord
            from app.modules.hrd.models import EmployeeEmergencyContact, EmploymentContract
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
            n_contacts = (
                db.query(EmployeeEmergencyContact)
                .filter(EmployeeEmergencyContact.employee_id == emp.id)
                .delete(synchronize_session=False)
            )
            # Kontrak bisa berantai (previous_contract_id) -- hapus dari ujung
            # rantai (yang tidak dirujuk kontrak lain) berulang kali sampai
            # habis, supaya tidak pernah menghapus induk sebelum anaknya.
            n_contracts = 0
            while True:
                leaf_ids = [
                    c.id
                    for c in db.query(EmploymentContract)
                    .filter(EmploymentContract.employee_id == emp.id)
                    .all()
                    if not db.query(EmploymentContract)
                    .filter(EmploymentContract.previous_contract_id == c.id)
                    .first()
                ]
                if not leaf_ids:
                    break
                n_contracts += (
                    db.query(EmploymentContract)
                    .filter(EmploymentContract.id.in_(leaf_ids))
                    .delete(synchronize_session=False)
                )
            db.commit()
            print(
                f"  [-] {emp.employee_no}: {n_records} record absensi, {n_summaries} rekap "
                f"bulanan, {n_contracts} kontrak, {n_contacts} kontak darurat dihapus"
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

        # ---------- 2) Rantai rekrutmen dummy: placement -> job order/candidate ----------
        from app.modules.recruitment.models import Candidate, JobOrder, Placement

        placements = (
            db.query(Placement)
            .join(Candidate, Placement.candidate_id == Candidate.id)
            .filter(Candidate.full_name.like("Dummy%"))
            .all()
        )
        for p in placements:
            leftover = referencing_row_counts(db, "placements", p.id)
            if leftover:
                print(f"  [!] placement {p.id} masih direferensikan {leftover} -- DILEWATI")
                continue
            db.delete(p)
        db.commit()
        if placements:
            print(f"  [-] {len(placements)} placement dummy dihapus")

        job_orders = db.query(JobOrder).filter(JobOrder.title.like("%(Dummy%")).all()
        for jo in job_orders:
            leftover = referencing_row_counts(db, "job_orders", jo.id)
            if leftover:
                print(f"  [!] job order '{jo.title}' masih direferensikan {leftover} -- DILEWATI")
                continue
            db.delete(jo)
            print(f"  [-] job order '{jo.title}' dihapus")
        db.commit()

        candidates = db.query(Candidate).filter(Candidate.full_name.like("Dummy%")).all()
        for c in candidates:
            leftover = referencing_row_counts(db, "candidates", c.id)
            if leftover:
                print(f"  [!] kandidat '{c.full_name}' masih direferensikan {leftover} -- DILEWATI")
                continue
            db.delete(c)
            print(f"  [-] kandidat '{c.full_name}' dihapus")
        db.commit()

        # ---------- 3) Client/site dummy ----------
        from app.modules.clients.models import Client, ClientSite

        clients = db.query(Client).filter(Client.name.like("Dummy%")).all()
        for cl in clients:
            sites = db.query(ClientSite).filter(ClientSite.client_id == cl.id).all()
            for s in sites:
                leftover = referencing_row_counts(db, "client_sites", s.id)
                if leftover:
                    print(f"  [!] site '{s.name}' masih direferensikan {leftover} -- DILEWATI")
                    continue
                db.delete(s)
                print(f"  [-] site '{s.name}' dihapus")
            db.commit()

            leftover = referencing_row_counts(db, "clients", cl.id)
            if leftover:
                print(f"  [!] client '{cl.name}' masih direferensikan {leftover} -- DILEWATI")
                continue
            db.delete(cl)
            db.commit()
            print(f"  [-] client '{cl.name}' dihapus")

        # ---------- 4) Akun dummy ----------
        users = db.query(User).filter(User.email.like("dummy-%")).all()
        for user in users:
            leftover = referencing_row_counts(db, "users", user.id)
            if leftover:
                print(
                    f"  [!] akun {user.email} masih direferensikan tabel lain {leftover} "
                    "-- DILEWATI (nonaktifkan manual lewat halaman Pengguna kalau perlu)."
                )
                continue
            db.delete(user)
            db.commit()
            print(f"  [-] akun {user.email} dihapus")

        print("\nSelesai membersihkan data dummy.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
