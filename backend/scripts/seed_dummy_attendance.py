"""Seed data tes/dummy: akun pengguna lintas role + absensi harian.

Dipakai untuk uji manual di browser (mis. verifikasi RBAC halaman Absensi):
membuat akun tiap role yang relevan, dua karyawan (internal + eksternal),
dan record absensi sebulan berjalan supaya "Rekap Bulanan" & validasi dua
jalur langsung ada isinya.

Jalan lewat HTTP ke server yang SUDAH BERJALAN (bukan tulis DB langsung) --
supaya lewat jalur validasi/RBAC/audit-log yang sama persis dengan pemakaian
asli, dan otomatis jadi smoke test untuk endpoint yang dipakai.

Semua data dummy diberi label jelas (nama diawali "Dummy", email di domain
@dummy.test) supaya gampang dikenali/dihapus lagi nanti. Idempotent: aman
dijalankan berkali-kali (re-run melewati akun/karyawan yang sudah ada,
timpa ulang record absensi tanggal yang sama alih-alih duplikat).

Pakai: .venv/Scripts/python scripts/seed_dummy_attendance.py
"""

from __future__ import annotations

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "dummy-seed-admin@outsourcing.co.id"
ADMIN_PASSWORD = "Dummy1234!"
DUMMY_PASSWORD = "Dummy1234!"

# role -> (email, nama, label singkat buat print ringkasan)
# Domain ".test"/".example"/".invalid" ditolak validator email (reserved
# TLD) -- dummy tetap ditandai lewat prefix "dummy-" di local-part, domain
# ikut konvensi tenant contoh yang sudah dipakai test suite (outsourcing.co.id).
DUMMY_ACCOUNTS = {
    "hr": ("dummy-hr@outsourcing.co.id", "Dummy HR"),
    "operations": ("dummy-ops@outsourcing.co.id", "Dummy Operations"),
    "management": ("dummy-mgmt@outsourcing.co.id", "Dummy Management"),
    "recruiter": (
        "dummy-recruiter@outsourcing.co.id",
        "Dummy Recruiter",
    ),  # kontrol negatif: TIDAK boleh akses Absensi
    "karyawan": ("dummy-karyawan@outsourcing.co.id", "Dummy Karyawan"),
}

YEAR, MONTH = 2026, 9

ATTENDANCE_INTERNAL = [
    ("2026-09-01", "hadir", "07:55", "17:05", 0, None),
    ("2026-09-02", "hadir", "07:58", "17:00", 0, None),
    ("2026-09-03", "terlambat", "08:45", "17:10", 0, None),
    ("2026-09-04", "sakit", None, None, 0, "Demam, surat dokter menyusul"),
    ("2026-09-07", "hadir", "07:50", "17:00", 0, None),
    ("2026-09-08", "hadir", "07:55", "19:00", 2, None),
    ("2026-09-09", "izin", None, None, 0, "Urus dokumen keluarga"),
    ("2026-09-10", "hadir", "07:52", "17:03", 0, None),
    ("2026-09-11", "alpa", None, None, 0, "Data dummy -- tanpa keterangan"),
]

ATTENDANCE_EKSTERNAL = [
    ("2026-09-01", "hadir", "08:00", "17:00", 0, None),
    ("2026-09-02", "dinas_luar", "08:00", "17:00", 0, "Kunjungan site klien"),
    ("2026-09-03", "hadir", "07:58", "17:02", 0, None),
    ("2026-09-04", "cuti", None, None, 0, "Cuti tahunan"),
    ("2026-09-07", "hadir", "08:01", "17:00", 0, None),
    ("2026-09-08", "hadir", "07:59", "17:05", 0, None),
    ("2026-09-09", "terlambat", "09:10", "17:15", 0, None),
    ("2026-09-10", "hadir", "08:00", "17:00", 0, None),
    ("2026-09-11", "hadir", "07:55", "20:00", 3, None),
]


def login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def ensure_account(
    client: httpx.Client, admin_headers: dict, role: str, email: str, name: str
) -> None:
    resp = client.post(
        "/auth/register",
        headers=admin_headers,
        json={"email": email, "full_name": name, "password": DUMMY_PASSWORD, "role": role},
    )
    if resp.status_code == 201:
        print(f"  [+] akun dibuat: {email} ({role})")
    elif resp.status_code == 409:
        print(f"  [=] akun sudah ada: {email} ({role})")
    else:
        resp.raise_for_status()


def ensure_employee(
    client: httpx.Client,
    admin_headers: dict,
    *,
    employee_no: str,
    full_name: str,
    employment_type: str,
) -> dict:
    existing = client.get("/employees", headers=admin_headers).json()
    for e in existing:
        if e["employee_no"] == employee_no:
            print(f"  [=] karyawan sudah ada: {employee_no} ({full_name})")
            return e
    resp = client.post(
        "/employees",
        headers=admin_headers,
        json={
            "full_name": full_name,
            "employee_no": employee_no,
            "employment_type": employment_type,
            "join_date": "2026-01-06",
        },
    )
    resp.raise_for_status()
    print(f"  [+] karyawan dibuat: {employee_no} ({full_name})")
    return resp.json()


def link_employee_to_account(
    client: httpx.Client, admin_headers: dict, employee_id: str, user_email: str
) -> None:
    users = client.get("/auth/users", headers=admin_headers).json()
    match = next((u for u in users if u["email"] == user_email), None)
    if match is None:
        print(f"  [!] tidak ketemu akun {user_email} buat ditautkan -- lewati")
        return
    resp = client.patch(
        f"/employees/{employee_id}", headers=admin_headers, json={"user_id": match["id"]}
    )
    resp.raise_for_status()
    print(f"  [+] karyawan ditautkan ke akun {user_email}")


def set_shift(
    client: httpx.Client, admin_headers: dict, employee_id: str, start: str, end: str
) -> None:
    resp = client.patch(
        f"/employees/{employee_id}",
        headers=admin_headers,
        json={"shift_start_time": start, "shift_end_time": end},
    )
    resp.raise_for_status()


def seed_attendance(
    client: httpx.Client, admin_headers: dict, employee_id: str, rows: list
) -> None:
    for day, status, clock_in, clock_out, overtime, notes in rows:
        resp = client.post(
            "/attendance/records",
            headers=admin_headers,
            json={
                "employee_id": employee_id,
                "date": day,
                "status": status,
                "clock_in": f"{day} {clock_in}" if clock_in else None,
                "clock_out": f"{day} {clock_out}" if clock_out else None,
                "overtime_hours": overtime,
                "notes": notes,
            },
        )
        resp.raise_for_status()
    print(f"  [+] {len(rows)} record absensi diisi utk {employee_id}")


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        try:
            admin_headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        except httpx.HTTPStatusError:
            print(
                f"Gagal login admin ({ADMIN_EMAIL}). Kalau kredensial admin lokal beda dari "
                "default (admin@example.com / admin1234), edit ADMIN_EMAIL/ADMIN_PASSWORD "
                "di puncak skrip ini lalu jalankan ulang.",
                file=sys.stderr,
            )
            return 1

        print("1) Akun dummy lintas role")
        for role, (email, name) in DUMMY_ACCOUNTS.items():
            ensure_account(client, admin_headers, role, email, name)

        print("\n2) Karyawan dummy")
        internal = ensure_employee(
            client,
            admin_headers,
            employee_no="DUMMY-001",
            full_name="Dummy Karyawan Internal",
            employment_type="internal",
        )
        eksternal = ensure_employee(
            client,
            admin_headers,
            employee_no="DUMMY-002",
            full_name="Dummy Karyawan Eksternal",
            employment_type="eksternal",
        )
        set_shift(client, admin_headers, internal["id"], "08:00", "17:00")
        link_employee_to_account(
            client, admin_headers, internal["id"], DUMMY_ACCOUNTS["karyawan"][0]
        )

        print("\n3) Record absensi harian (Sep 2026)")
        seed_attendance(client, admin_headers, internal["id"], ATTENDANCE_INTERNAL)
        seed_attendance(client, admin_headers, eksternal["id"], ATTENDANCE_EKSTERNAL)

        print("\nSelesai. Kredensial buat login manual di browser:\n")
        print(f"  {'role':<12} {'email':<24} password")
        print(f"  {'-' * 12} {'-' * 24} --------")
        for role, (email, _name) in DUMMY_ACCOUNTS.items():
            print(f"  {role:<12} {email:<24} {DUMMY_PASSWORD}")
        print(
            "\nBuka /attendance login sbg hr/operations/management -> harus bisa lihat & "
            "validasi rekap. Login sbg karyawan/recruiter -> menu Absensi harus HILANG dari "
            "sidebar, dan panggilan API langsung ke endpoint itu harus 403."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
