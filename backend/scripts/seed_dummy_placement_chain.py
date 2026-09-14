"""Lengkapi rantai rekrutmen dummy supaya ADA satu karyawan eksternal yang
benar-benar tercatat di tab Karyawan klien "Dummy Klien Outsourcing" --
bukan cuma tertaut lewat `site_id` (geofencing) seperti DUMMY-002, tapi juga
lewat `placement_id` (yang dibaca `list_client_employees`,
`clients/service.py:172-191`).

`Employee.placement_id` immutable setelah dibuat (tidak ada di
`EmployeeUpdate`), jadi DUMMY-002 TIDAK bisa dikonversi -- karyawan baru
(DUMMY-003) dibuat lewat alur rekrutmen sungguhan: Candidate -> JobOrder
(milik klien dummy) -> Placement -> onboard. Site geofencing-nya ditaut ke
site dummy yang sama dengan DUMMY-002.

Lewat HTTP ke server yang sudah jalan, pakai akun
`dummy-seed-admin@outsourcing.co.id`. Idempotent -- aman dijalankan ulang.
Butuh `seed_dummy_client_site.py` sudah pernah dijalankan.

Pakai: .venv/Scripts/python scripts/seed_dummy_placement_chain.py
"""

from __future__ import annotations

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "dummy-seed-admin@outsourcing.co.id"
ADMIN_PASSWORD = "Dummy1234!"

CLIENT_NAME = "Dummy Klien Outsourcing"
SITE_NAME = "Kantor Pusat (Dummy)"
CANDIDATE_NAME = "Dummy Kandidat Onboarded"
JOB_ORDER_TITLE = "Staff Operasional (Dummy)"
EMPLOYEE_NO = "DUMMY-003"


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
        already = next((e for e in employees if e["employee_no"] == EMPLOYEE_NO), None)
        if already is not None:
            print(f"  [=] {EMPLOYEE_NO} sudah ada, tidak dibuat ulang.")
            emp = already
        else:
            clients = client.get("/clients", headers=headers).json()
            dummy_client = next((c for c in clients if c["name"] == CLIENT_NAME), None)
            if dummy_client is None:
                print(
                    f"Client '{CLIENT_NAME}' belum ada -- jalankan seed_dummy_client_site.py dulu.",
                    file=sys.stderr,
                )
                return 1
            print(f"  [=] client: {CLIENT_NAME} ({dummy_client['id']})")

            sites = client.get(f"/clients/{dummy_client['id']}/sites", headers=headers).json()
            dummy_site = next((s for s in sites if s["name"] == SITE_NAME), None)
            if dummy_site is None:
                print(
                    f"Site '{SITE_NAME}' belum ada -- jalankan seed_dummy_client_site.py dulu.",
                    file=sys.stderr,
                )
                return 1

            candidates = client.get("/recruitment/candidates", headers=headers).json()
            candidate = next((c for c in candidates if c["full_name"] == CANDIDATE_NAME), None)
            if candidate is None:
                resp = client.post(
                    "/recruitment/candidates",
                    headers=headers,
                    json={
                        "full_name": CANDIDATE_NAME,
                        "phone": "081200000000",
                        "email": "dummy.kandidat@outsourcing.co.id",
                        "source": "Data tes",
                    },
                )
                resp.raise_for_status()
                candidate = resp.json()
                print(f"  [+] kandidat dibuat: {CANDIDATE_NAME}")
            else:
                print(f"  [=] kandidat sudah ada: {CANDIDATE_NAME}")

            job_orders = client.get(
                "/recruitment/job-orders", headers=headers, params={"client_id": dummy_client["id"]}
            ).json()
            job_order = next((j for j in job_orders if j["title"] == JOB_ORDER_TITLE), None)
            if job_order is None:
                resp = client.post(
                    "/recruitment/job-orders",
                    headers=headers,
                    json={
                        "client_id": dummy_client["id"],
                        "title": JOB_ORDER_TITLE,
                        "headcount": 1,
                        "description": "Job order data tes",
                    },
                )
                resp.raise_for_status()
                job_order = resp.json()
                print(f"  [+] job order dibuat: {JOB_ORDER_TITLE}")
            else:
                print(f"  [=] job order sudah ada: {JOB_ORDER_TITLE}")

            placements = client.get("/recruitment/placements", headers=headers).json()
            placement = next(
                (
                    p
                    for p in placements
                    if p["candidate_id"] == candidate["id"] and p["job_order_id"] == job_order["id"]
                ),
                None,
            )
            if placement is None:
                resp = client.post(
                    "/recruitment/placements",
                    headers=headers,
                    json={
                        "candidate_id": candidate["id"],
                        "job_order_id": job_order["id"],
                        "start_date": "2026-09-01",
                    },
                )
                resp.raise_for_status()
                placement = resp.json()
                print("  [+] placement dibuat")
            else:
                print("  [=] placement sudah ada")

            resp = client.post(
                "/employees/onboard",
                headers=headers,
                json={
                    "placement_id": placement["id"],
                    "employee_no": EMPLOYEE_NO,
                    "join_date": "2026-09-01",
                    "phone": "081200000000",
                },
            )
            resp.raise_for_status()
            emp = resp.json()
            print(f"  [+] onboarding selesai: {EMPLOYEE_NO} ({emp['full_name']})")

            # employment_type default sudah "eksternal" (kolom model), tapi
            # dipastikan eksplisit -- query roster klien mensyaratkan ini.
            client.patch(
                f"/employees/{emp['id']}", headers=headers, json={"employment_type": "eksternal"}
            ).raise_for_status()

        # Tautkan site yang sama dgn DUMMY-002 supaya geofencing juga aktif.
        clients = client.get("/clients", headers=headers).json()
        dummy_client = next(c for c in clients if c["name"] == CLIENT_NAME)
        sites = client.get(f"/clients/{dummy_client['id']}/sites", headers=headers).json()
        dummy_site = next(s for s in sites if s["name"] == SITE_NAME)
        if emp.get("site_id") != dummy_site["id"]:
            client.patch(
                f"/employees/{emp['id']}", headers=headers, json={"site_id": dummy_site["id"]}
            ).raise_for_status()
            print(f"  [+] {EMPLOYEE_NO} ditautkan ke site '{SITE_NAME}'")

        roster = client.get(f"/clients/{dummy_client['id']}/employees", headers=headers).json()
        in_roster = any(e["id"] == emp["id"] for e in roster)
        status = "MUNCUL" if in_roster else "BELUM muncul (ada yang salah)"
        print(
            f"\nVerifikasi tab Karyawan klien '{CLIENT_NAME}': "
            f"{status} -- {len(roster)} karyawan total."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
