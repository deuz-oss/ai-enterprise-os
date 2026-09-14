"""Tambah riwayat absensi lintas bulan utk karyawan dummy (DUMMY-001, tertaut
ke akun dummy-karyawan@outsourcing.co.id) -- pelengkap `seed_dummy_attendance.py`
yang cuma mengisi bulan berjalan (Sep 2026).

Kenapa terpisah: skrip awal cuma 1 bulan (belum jadi "riwayat" kalau dibuka
lewat date-picker di Portal Saya -> Absensi -> Rekap Kehadiran, yang
menampilkan satu periode dari input tahun/bulan). Skrip ini menambah Jun-Ags
2026 supaya ada beberapa bulan buat dipaging, dan memvalidasi satu bulan
(Agustus) lewat jalur HR supaya riwayatnya juga menunjukkan status
"disetujui", bukan "menunggu" semua.

Butuh `seed_dummy_attendance.py` sudah pernah dijalankan (akun
dummy-seed-admin & karyawan DUMMY-001 sudah ada). Idempotent -- aman
dijalankan ulang.

Pakai: .venv/Scripts/python scripts/seed_dummy_attendance_history.py
"""

from __future__ import annotations

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "dummy-seed-admin@outsourcing.co.id"
ADMIN_PASSWORD = "Dummy1234!"
EMPLOYEE_NO = "DUMMY-001"

# (tanggal, status, clock_in, clock_out, overtime_hours, catatan)
HISTORY = {
    6: [
        ("2026-06-01", "hadir", "07:57", "17:02", 0, None),
        ("2026-06-02", "hadir", "07:50", "17:00", 0, None),
        ("2026-06-03", "izin", None, None, 0, "Antar keluarga ke RS"),
        ("2026-06-04", "hadir", "08:10", "17:15", 0, None),
        ("2026-06-05", "hadir", "07:55", "19:30", 2, None),
    ],
    7: [
        ("2026-07-01", "hadir", "07:58", "17:00", 0, None),
        ("2026-07-02", "hadir", "07:52", "17:05", 0, None),
        ("2026-07-03", "cuti", None, None, 0, "Cuti tahunan"),
        ("2026-07-06", "hadir", "07:59", "17:01", 0, None),
        ("2026-07-07", "terlambat", "08:40", "17:00", 0, None),
    ],
    8: [
        ("2026-08-03", "hadir", "07:55", "17:05", 0, None),
        ("2026-08-04", "hadir", "07:58", "17:00", 0, None),
        ("2026-08-05", "hadir", "07:50", "18:30", 1, None),
        ("2026-08-06", "sakit", None, None, 0, "Flu, 1 hari"),
        ("2026-08-07", "hadir", "07:57", "17:02", 0, None),
    ],
}
VALIDATE_MONTH = 8  # bulan yang divalidasi (lengkap, sudah "tutup buku")


def login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        try:
            headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        except httpx.HTTPStatusError:
            print(
                f"Gagal login {ADMIN_EMAIL} -- jalankan seed_dummy_attendance.py dulu.",
                file=sys.stderr,
            )
            return 1

        employees = client.get("/employees", headers=headers).json()
        emp = next((e for e in employees if e["employee_no"] == EMPLOYEE_NO), None)
        if emp is None:
            print(
                f"Karyawan {EMPLOYEE_NO} belum ada -- jalankan seed_dummy_attendance.py dulu.",
                file=sys.stderr,
            )
            return 1

        for month, rows in HISTORY.items():
            for day, status, clock_in, clock_out, overtime, notes in rows:
                resp = client.post(
                    "/attendance/records",
                    headers=headers,
                    json={
                        "employee_id": emp["id"],
                        "date": day,
                        "status": status,
                        "clock_in": f"{day} {clock_in}" if clock_in else None,
                        "clock_out": f"{day} {clock_out}" if clock_out else None,
                        "overtime_hours": overtime,
                        "notes": notes,
                    },
                )
                resp.raise_for_status()
            print(f"  [+] {len(rows)} record absensi diisi utk bulan {month}/2026")

        summaries = client.get(
            "/payroll/attendance",
            headers=headers,
            params={"year": 2026, "month": VALIDATE_MONTH},
        ).json()
        target = next((s for s in summaries if s["employee_id"] == emp["id"]), None)
        if target and not target["client_approved"]:
            resp = client.post(
                f"/attendance/summaries/{target['id']}/validate",
                headers=headers,
                params={"lane": "hr"},
            )
            resp.raise_for_status()
            print(f"  [+] rekap {VALIDATE_MONTH}/2026 divalidasi (jalur HR)")
        else:
            print(f"  [=] rekap {VALIDATE_MONTH}/2026 sudah tervalidasi sebelumnya")

        print(
            "\nSelesai. Login sbg dummy-karyawan@outsourcing.co.id -> Portal Saya -> "
            "Absensi -> Rekap Kehadiran, ganti bulan (6/7/8/9-2026) buat lihat riwayatnya."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
