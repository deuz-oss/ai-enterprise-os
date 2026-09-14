"""Lengkapi tautan klien buat DUMMY-002 ("Dummy Karyawan Eksternal"):
buat 1 Client dummy + 1 ClientSite dummy, lalu set `Employee.site_id` supaya
geofencing absensi (Fase 34) aktif utknya -- sebelumnya cuma berlabel
"eksternal" tanpa tautan apa pun, lihat percakapan sebelumnya.

Lewat HTTP ke server yang sudah jalan (bukan tulis DB langsung), pakai akun
`dummy-seed-admin@outsourcing.co.id` dari `seed_dummy_attendance.py`.
Idempotent -- aman dijalankan ulang.

Pakai: .venv/Scripts/python scripts/seed_dummy_client_site.py
"""

from __future__ import annotations

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "dummy-seed-admin@outsourcing.co.id"
ADMIN_PASSWORD = "Dummy1234!"

CLIENT_NAME = "Dummy Klien Outsourcing"
SITE_NAME = "Kantor Pusat (Dummy)"
# Monas, Jakarta Pusat -- titik gampang dikenali, cuma buat data tes.
SITE_LAT = -6.175392
SITE_LNG = 106.827153
SITE_RADIUS_M = 150

EMPLOYEE_NO = "DUMMY-002"


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

        clients = client.get("/clients", headers=headers).json()
        dummy_client = next((c for c in clients if c["name"] == CLIENT_NAME), None)
        if dummy_client is None:
            resp = client.post(
                "/clients",
                headers=headers,
                json={
                    "name": CLIENT_NAME,
                    "address": "Jl. Dummy Raya No. 1, Jakarta Pusat (data tes)",
                    "pic_name": "Dummy PIC",
                },
            )
            resp.raise_for_status()
            dummy_client = resp.json()
            print(f"  [+] client dibuat: {CLIENT_NAME} ({dummy_client['id']})")
        else:
            print(f"  [=] client sudah ada: {CLIENT_NAME} ({dummy_client['id']})")

        sites = client.get(f"/clients/{dummy_client['id']}/sites", headers=headers).json()
        dummy_site = next((s for s in sites if s["name"] == SITE_NAME), None)
        if dummy_site is None:
            resp = client.post(
                f"/clients/{dummy_client['id']}/sites",
                headers=headers,
                json={
                    "name": SITE_NAME,
                    "address": "Monas, Jakarta Pusat (data tes)",
                    "latitude": SITE_LAT,
                    "longitude": SITE_LNG,
                    "radius_meters": SITE_RADIUS_M,
                },
            )
            resp.raise_for_status()
            dummy_site = resp.json()
            print(f"  [+] site dibuat: {SITE_NAME} (radius {SITE_RADIUS_M}m)")
        else:
            print(f"  [=] site sudah ada: {SITE_NAME}")

        employees = client.get("/employees", headers=headers).json()
        emp = next((e for e in employees if e["employee_no"] == EMPLOYEE_NO), None)
        if emp is None:
            print(
                f"Karyawan {EMPLOYEE_NO} belum ada -- jalankan seed_dummy_attendance.py dulu.",
                file=sys.stderr,
            )
            return 1

        resp = client.patch(
            f"/employees/{emp['id']}", headers=headers, json={"site_id": dummy_site["id"]}
        )
        resp.raise_for_status()
        print(f"  [+] {EMPLOYEE_NO} ditautkan ke site '{SITE_NAME}' milik '{CLIENT_NAME}'")

        print(
            "\nSelesai. Cek di UI: Karyawan -> Dummy Karyawan Eksternal -> field "
            "'Lokasi Kerja' sekarang menampilkan 'Dummy Klien Outsourcing — "
            "Kantor Pusat (Dummy)'.\n"
            "Efek ke absensi mobile (kalau dicoba dari app): clock-in/out di luar "
            f"radius {SITE_RADIUS_M}m dari titik Monas akan ditolak 422 -- "
            "sebelumnya (site_id kosong) absen selalu bebas tanpa cek lokasi."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
