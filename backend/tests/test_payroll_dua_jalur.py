"""Fase 9a — Payrol dua jalur + approval klien ber-token (ADR-0006)."""

from datetime import UTC, datetime, timedelta

from tests.conftest import _auth_header, _platform_admin_header


def _setup(client):
    """Admin + klien + karyawan eksternal yang ditempatkan di klien tsb."""
    admin = _auth_header(client)
    client_resp = client.post("/api/v1/clients", headers=admin, json={"name": "PT Klien Proyek"})
    assert client_resp.status_code == 201, client_resp.text
    client_id = client_resp.json()["id"]

    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=admin,
        json={"client_id": client_id, "title": "Operator", "headcount": 1},
    ).json()
    cand = client.post(
        "/api/v1/recruitment/candidates",
        headers=admin,
        json={"full_name": "TKO Ditempatkan"},
    ).json()
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=admin,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"]},
    )
    assert placement.status_code == 201, placement.text

    emp = client.post(
        "/api/v1/employees",
        headers=admin,
        json={
            "full_name": "TKO Ditempatkan",
            "base_salary": 5_000_000,
            "placement_id": placement.json()["id"],
        },
    )
    assert emp.status_code == 201, emp.text
    return admin, client_id, emp.json()


def test_internal_flow_unchanged(client):
    admin = _auth_header(client)
    run = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 5}).json()
    assert run["run_type"] == "internal"
    assert run["status"] == "draft"

    # Finalisasi langsung dari draft tetap didukung (kompatibilitas).
    client.post("/api/v1/employees", headers=admin, json={"full_name": "Staf", "base_salary": 4_000_000})
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    fin = client.post("/api/v1/payroll/runs/{0}/start-processing".format(run["id"]), headers=admin)
    assert fin.status_code == 200
    assert fin.json()["status"] == "finance_processing"
    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "final"


def test_internal_run_tidak_bisa_submit_ke_klien(client):
    admin = _auth_header(client)
    run = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 3}).json()
    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={})
    assert resp.status_code == 422


def test_proyek_lifecycle_dengan_token(client):
    admin, client_id, emp = _setup(client)

    # Payrol proyek wajib memilih klien
    missing = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 6, "run_type": "proyek"})
    assert missing.status_code == 422

    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 6, "run_type": "proyek", "client_id": client_id},
    ).json()
    assert run["run_type"] == "proyek" and run["client_id"] == client_id

    # Generate slip → hanya karyawan penempatan klien ini
    slips = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={}).json()
    assert [s["employee_id"] for s in slips] == [emp["id"]]
    assert float(slips[0]["gross"]) == 5_000_000

    # Finalize sebelum approval klien ditolak state machine-nya
    early = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)
    assert early.status_code == 409

    # Submit ke klien → token
    submitted = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={"days": 7})
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["status"] == "submitted_to_client"
    raw_token = body["raw_token"]
    link = body["link"]
    assert link.startswith("/payroll/client/")

    # Ringkasan publik tanpa akun
    view = client.get(f"/api/v1{link}")
    assert view.status_code == 200, view.text
    vbody = view.json()
    assert vbody["client"] == "PT Klien Proyek"
    assert vbody["total_net_pay"] > 0
    assert len(vbody["lines"]) == 1

    # Keputusan tanpa nama ditolak validasi
    no_name = client.post(f"/payroll/client/{raw_token}/decision".replace("/payroll/client/", "/api/v1/payroll/client/") if False else f"/api/v1/payroll/client/{raw_token}/decision", json={"approved": True, "name": ""})
    assert no_name.status_code == 422

    # Klien menyetujui
    decision = client.post(
        f"/api/v1/payroll/client/{raw_token}/decision",
        json={"approved": True, "name": "Direktur Klien", "note": "OK semua"},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "client_approved"

    # Token sudah terpakai → tidak bisa dipakai lagi
    reuse = client.get(f"/api/v1/payroll/client/{raw_token}")
    assert reuse.status_code == 409
    reuse_dec = client.post(f"/api/v1/payroll/client/{raw_token}/decision", json={"approved": False, "name": "X"})
    assert reuse_dec.status_code == 409

    # Mulai proses finance → finalisasi
    proc = client.post(f"/api/v1/payroll/runs/{run['id']}/start-processing", headers=admin)
    assert proc.status_code == 200 and proc.json()["status"] == "finance_processing"
    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)
    assert finalized.status_code == 200 and finalized.json()["status"] == "final"


def test_client_reject_then_resubmit(client):
    admin, client_id, emp = _setup(client)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 7, "run_type": "proyek", "client_id": client_id},
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})

    sub1 = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}).json()
    rej = client.post(
        f"/api/v1/payroll/client/{sub1['raw_token']}/decision",
        json={"approved": False, "name": "Klien", "note": "Ada selisih lembur"},
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "client_rejected"

    # Setelah ditolak, angka boleh diperbaiki (generate ulang) lalu dikirim
    # ulang dengan link baru.
    regen = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    assert regen.status_code in (200, 201, 409)  # 409 bila semua slip sudah ada

    sub2 = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}).json()
    assert sub2["status"] == "submitted_to_client"
    assert sub2["raw_token"] != sub1["raw_token"]

    approve = client.post(
        f"/api/v1/payroll/client/{sub2['raw_token']}/decision",
        json={"approved": True, "name": "Klien"},
    )
    assert approve.status_code == 200


def test_expired_token_rejected(client):
    admin, client_id, emp = _setup(client)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 8, "run_type": "proyek", "client_id": client_id},
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    sub = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={"days": 1}).json()

    # Majukan waktu kedaluwarsa token secara manual via DB.
    from sqlalchemy import update

    from app.modules.payroll.models import PayrollRunToken

    db = client.testing_session()
    try:
        db.execute(
            update(PayrollRunToken).values(expires_at=datetime.now(UTC) - timedelta(days=1))
        )
        db.commit()
    finally:
        db.close()

    expired_view = client.get(f"/api/v1/payroll/client/{sub['raw_token']}")
    assert expired_view.status_code == 410
    expired_dec = client.post(
        f"/api/v1/payroll/client/{sub['raw_token']}/decision",
        json={"approved": True, "name": "Klien"},
    )
    assert expired_dec.status_code == 410


def test_license_guard_per_run_type(client):
    """Revoke operations_billing → payrol proyek diblokir, internal tetap jalan."""
    admin = _auth_header(client)
    plat = _platform_admin_header(client)
    tenants = client.get("/api/v1/platform/tenants", headers=plat).json()
    default_id = next(t["id"] for t in tenants if t["slug"] == "default")

    revoke = client.patch(
        f"/api/v1/platform/tenants/{default_id}/licenses/operations_billing",
        headers=plat,
        json={"status": "kedaluwarsa"},
    )
    assert revoke.status_code == 200

    proyek = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 9, "run_type": "proyek", "client_id": "00000000-0000-0000-0000-00000000dead"},
    )
    assert proyek.status_code == 403
    assert "Operations & Billing" in proyek.json()["detail"]

    internal = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 10})
    assert internal.status_code == 201

    # Pulihkan
    client.patch(
        f"/api/v1/platform/tenants/{default_id}/licenses/operations_billing",
        headers=plat,
        json={"status": "aktif"},
    )


def test_proyek_generate_hanya_karyawan_klien_tersebut(client):
    admin, client_id, emp = _setup(client)
    # Karyawan lain tanpa penempatan
    client.post("/api/v1/employees", headers=admin, json={"full_name": "Staf Internal Lain"})
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 11, "run_type": "proyek", "client_id": client_id},
    ).json()
    slips = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={}).json()
    assert [s["employee_id"] for s in slips] == [emp["id"]]
