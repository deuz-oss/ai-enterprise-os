"""Fase 9c — Workflow Payment Request (PRD §7)."""

from tests.conftest import _auth_header


def _finalized_run(client, headers, year=2026, month=5, salary=6_000_000):
    client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "PR Emp", "base_salary": salary}
    ).json()
    run = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": year, "month": month}
    ).json()
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
    rejected_only = client.get("/api/v1/payment-requests?status=ditolak", headers=headers).json()
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
    sub = client.post(
        f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}
    ).json()
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


# ---------- Fase 9 penutup: rantai approval multi-level per tenant ----------


def _make_user(client, admin_headers, email, role):
    created = client.post(
        "/api/v1/auth/register",
        headers=admin_headers,
        json={
            "email": email,
            "full_name": email.split("@")[0].title(),
            "password": "rahasia-123",
            "role": role,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _login(client, email, password="rahasia-123"):
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_pr_multi_level_chain_role_then_user(client):
    headers = _auth_header(client)
    _make_user(client, headers, "mgmt-pr@example.com", "management")
    fin = _make_user(client, headers, "fin-pr@example.com", "finance")
    fin_h = _login(client, "fin-pr@example.com")
    mgmt_h = _login(client, "mgmt-pr@example.com")
    run = _finalized_run(client, headers)

    # Konfigurasi rantai: tahap 1 = peran management, tahap 2 = user finance spesifik
    put = client.put(
        "/api/v1/payment-requests/approval-chain",
        headers=headers,
        json={
            "steps": [
                {"approver_role": "management"},
                {"approver_id": fin["id"]},
            ]
        },
    )
    assert put.status_code == 200, put.text
    chain = client.get("/api/v1/payment-requests/approval-chain", headers=headers).json()
    assert [c["seq"] for c in chain] == [1, 2]
    assert chain[0]["approver_role"] == "management"
    assert chain[1]["approver_id"] == fin["id"]

    pr = client.post(
        "/api/v1/payment-requests",
        headers=headers,
        json={"pr_type": "internal", "payroll_run_id": run["id"], "description": "Rantai"},
    ).json()

    # Approver tahap 2 tidak bisa memutus di tahap 1
    wrong = client.post(f"/api/v1/payment-requests/{pr['id']}/approve", headers=fin_h)
    assert wrong.status_code == 403

    # Tahap 1: management menyetujui → PR masih menunggu (lanjut tahap 2)
    step1 = client.post(f"/api/v1/payment-requests/{pr['id']}/approve", headers=mgmt_h)
    assert step1.status_code == 200
    row = next(
        p
        for p in client.get("/api/v1/payment-requests", headers=headers).json()
        if p["id"] == pr["id"]
    )
    assert row["status"] == "menunggu_atasan"
    assert row["progress"]["total_steps"] == 2
    assert row["progress"]["current_step"] == 2
    assert len(row["progress"]["decisions"]) == 1

    # Tahap 2: user finance spesifik menyetujui → disetujui_atasan
    step2 = client.post(f"/api/v1/payment-requests/{pr['id']}/approve", headers=fin_h)
    assert step2.status_code == 200
    assert step2.json()["status"] == "disetujui_atasan"

    exe = client.post(f"/api/v1/payment-requests/{pr['id']}/execute", headers=fin_h)
    assert exe.status_code == 200
    assert exe.json()["status"] == "dieksekusi"


def test_pr_chain_reject_records_decision(client):
    headers = _auth_header(client)
    _make_user(client, headers, "mgmt-rej@example.com", "management")
    mgmt_h = _login(client, "mgmt-rej@example.com")
    run = _finalized_run(client, headers)

    res = client.put(
        "/api/v1/payment-requests/approval-chain",
        headers=headers,
        json={"steps": [{"approver_role": "management"}]},
    )
    assert res.status_code == 200

    pr = client.post(
        "/api/v1/payment-requests",
        headers=headers,
        json={"pr_type": "internal", "payroll_run_id": run["id"]},
    ).json()

    # Penolakan di satu tahap menggugurkan seluruh PR; catatan wajib
    no_note = client.post(
        f"/api/v1/payment-requests/{pr['id']}/reject", headers=mgmt_h, json={"note": ""}
    )
    assert no_note.status_code == 422

    rej = client.post(
        f"/api/v1/payment-requests/{pr['id']}/reject",
        headers=mgmt_h,
        json={"note": "Anggaran belum cair"},
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "ditolak"

    row = next(
        p
        for p in client.get("/api/v1/payment-requests?status=ditolak", headers=headers).json()
        if p["id"] == pr["id"]
    )
    assert row["decision_note"] == "Anggaran belum cair"
    assert row["progress"]["decisions"][0]["approved"] is False


def test_pr_chain_config_validation_and_reset(client):
    headers = _auth_header(client)
    _make_user(client, headers, "mgmt-cfg@example.com", "management")

    # Dua-duanya kosong / dua-duanya terisi → 422
    both_empty = client.put(
        "/api/v1/payment-requests/approval-chain",
        headers=headers,
        json={"steps": [{"approver_role": ""}]},
    )
    assert both_empty.status_code == 422
    both_filled = client.put(
        "/api/v1/payment-requests/approval-chain",
        headers=headers,
        json={"steps": [{"approver_id": "x", "approver_role": "management"}]},
    )
    assert both_filled.status_code in (404, 422)  # user tak dikenal / validasi format

    # Peran bukan staf ditolak
    bad_role = client.put(
        "/api/v1/payment-requests/approval-chain",
        headers=headers,
        json={"steps": [{"approver_role": "karyawan"}]},
    )
    assert bad_role.status_code == 422

    # Reset ke kosong → kembali perilaku legacy
    reset = client.put(
        "/api/v1/payment-requests/approval-chain", headers=headers, json={"steps": []}
    )
    assert reset.status_code == 200
    assert reset.json()["steps"] == []

    # Tanpa rantai: management mana pun tetap bisa memutus (legacy)
    run = _finalized_run(client, headers)
    pr = client.post(
        "/api/v1/payment-requests",
        headers=headers,
        json={"pr_type": "internal", "payroll_run_id": run["id"]},
    ).json()
    legacy = client.post(
        f"/api/v1/payment-requests/{pr['id']}/approve", headers=_auth_header(client)
    )
    assert legacy.status_code == 200
    assert legacy.json()["status"] == "disetujui_atasan"
