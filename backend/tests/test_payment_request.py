"""Fase 9c — Workflow Payment Request (PRD §7)."""

from tests.conftest import _auth_header


def _finalized_run(client, headers, year=2026, month=5, salary=6_000_000):
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "PR Emp", "base_salary": salary}
    ).json()
    run = client.post("/api/v1/payroll/runs", headers=headers, json={"year": year, "month": month}).json()
    gen = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert gen.status_code == 201, gen.text
    fin = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=headers)
    assert fin.status_code == 200
    return run


def test_pr_lifecycle_create_approve_execute(client):
    headers = _auth_header(client)  # role admin — bisa semua aksi
    run = _finalized_run(client, headers)

    created = client.post(
        "/api/v1/payment-requests",
        headers=headers,
        json={
            "pr_type": "internal",
            "payroll_run_id": run["id"],
            "description": "Gaji Mei 2026",
        },
    )
    assert created.status_code == 201, created.text
    pr = created.json()
    assert pr["pr_number"].startswith("PR/2026/")
    assert pr["status"] == "menunggu_atasan"

    # Amount default = Σ net_pay slip (auto dari run final)
    listed = client.get("/api/v1/payment-requests", headers=headers).json()
    row = next(p for p in listed if p["id"] == pr["id"])
    assert float(row["amount"]) > 0

    # Approve → eksekusi
    appr = client.post(f"/api/v1/payment-requests/{pr['id']}/approve", headers=headers)
    assert appr.status_code == 200
    assert appr.json()["status"] == "disetujui_atasan"

    exe = client.post(f"/api/v1/payment-requests/{pr['id']}/execute", headers=headers)
    assert exe.status_code == 200
    assert exe.json()["status"] == "dieksekusi"

    # Setelah dieksekusi tidak bisa diubah lagi
    again = client.post(f"/api/v1/payment-requests/{pr['id']}/approve", headers=headers)
    assert again.status_code == 409


def test_pr_reject_requires_note_and_resubmit_flow(client):
    headers = _auth_header(client)
    run = _finalized_run(client, headers)

    pr = client.post(
        "/api/v1/payment-requests",
        headers=headers,
        json={"pr_type": "internal", "payroll_run_id": run["id"]},
    ).json()

    # Tolak tanpa catatan ditolak validasi
    no_note = client.post(
        f"/api/v1/payment-requests/{pr['id']}/reject",
        headers=headers,
        json={"note": ""},
    )
    assert no_note.status_code == 422

    # Tolak dengan catatan → status ditolak; buat PR baru dari run yang sama
    rej = client.post(
        f"/api/v1/payment-requests/{pr['id']}/reject",
        headers=headers,
        json={"note": "Nominal kurang"},
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "ditolak"

    pr2 = client.post(
        "/api/v1/payment-requests",
        headers=headers,
        json={"pr_type": "internal", "payroll_run_id": run["id"], "description": "Revisi"},
    )
    assert pr2.status_code == 201

    # Filter status bekerja
    rejected_only = client.get(
        "/api/v1/payment-requests?status=ditolak", headers=headers
    ).json()
    assert all(p["status"] == "ditolak" for p in rejected_only)


def test_pr_from_proyek_run(client):
    from tests.test_payroll_dua_jalur import _setup

    admin, client_id, emp = _setup(client)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 12, "run_type": "proyek", "client_id": client_id},
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})

    # Run belum final → PR ditolak
    not_final = client.post(
        "/api/v1/payment-requests",
        headers=admin,
        json={"pr_type": "proyek", "payroll_run_id": run["id"]},
    )
    assert not_final.status_code == 422

    # Jalur proyek: submit ke klien & approve sebelum PR
    sub = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}).json()
    client.post(
        f"/api/v1/payroll/client/{sub['raw_token']}/decision",
        json={"approved": True, "name": "Klien"},
    )
    client.post(f"/api/v1/payroll/runs/{run['id']}/start-processing", headers=admin)
    fin = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)
    assert fin.status_code == 200

    # Invoice draft otomatis sudah dibuat saat approval
    invoices = client.get("/api/v1/finance/invoices", headers=admin).json()
    inv = next(i for i in invoices if i["client_id"] == client_id and i["month"] == 12)
    assert inv["payroll_total"] > 0

    # PR proyek dari run final
    pr = client.post(
        "/api/v1/payment-requests",
        headers=admin,
        json={"pr_type": "proyek", "payroll_run_id": run["id"]},
    ).json()
    assert pr["status"] == "menunggu_atasan"
