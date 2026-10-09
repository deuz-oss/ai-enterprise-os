"""Rekonsiliasi invoice ↔ absensi disetujui (finance/reconciliation.py)."""

from sqlalchemy import text

from tests.conftest import _auth_header


def _seed(client, headers, salary=5_000_000):
    """Klien → JO → kandidat → placement → karyawan; kembalikan (client_id, employee_id)."""
    client_id = client.post(
        "/api/v1/clients", headers=headers, json={"name": "PT Rekon Absensi"}
    ).json()["id"]
    jo_id = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Operator", "headcount": 1},
    ).json()["id"]
    cand_id = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Sari Wulandari"}
    ).json()["id"]
    placement_id = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    ).json()["id"]
    resp = client.post(
        "/api/v1/employees/onboard",
        headers=headers,
        json={"placement_id": placement_id, "base_salary": salary},
    )
    assert resp.status_code == 201, resp.text
    employee_id = resp.json()["id"]
    resp = client.patch(
        f"/api/v1/employees/{employee_id}", headers=headers, json={"base_salary": salary}
    )
    assert resp.status_code == 200, resp.text
    return client_id, employee_id


def _attendance(client, headers, employee_id, overtime, approve):
    resp = client.post(
        "/api/v1/payroll/attendance",
        headers=headers,
        json={
            "employee_id": employee_id,
            "year": 2026,
            "month": 7,
            "present_days": 21,
            "overtime_hours": overtime,
        },
    )
    assert resp.status_code == 201, resp.text
    if approve:
        resp = client.patch(
            f"/api/v1/payroll/attendance/{resp.json()['id']}/client-approval",
            headers=headers,
            params={"approved": True},
        )
        assert resp.status_code == 200, resp.text


def _run_and_invoice(client, headers, client_id):
    run_id = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 7}
    ).json()["id"]
    resp = client.post(
        f"/api/v1/payroll/runs/{run_id}/generate",
        headers=headers,
        json={"overtime_rate": 50_000},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 7, "fee_amount": 1_000_000},
    )
    assert resp.status_code == 201, resp.text
    return run_id, resp.json()["id"]


def _recon(client, headers, invoice_id):
    resp = client.get(f"/api/v1/finance/invoices/{invoice_id}/reconciliation", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_reconciliation_clean_when_billing_matches_approved_attendance(client):
    headers = _auth_header(client)
    client_id, employee_id = _seed(client, headers)
    _attendance(client, headers, employee_id, overtime=5, approve=True)
    _, invoice_id = _run_and_invoice(client, headers, client_id)

    rec = _recon(client, headers, invoice_id)
    assert rec["findings"] == [], rec["findings"]
    assert rec["totals"]["headcount_billed"] == 1
    assert rec["totals"]["headcount_approved"] == 1
    assert rec["totals"]["overtime_billed"] == rec["totals"]["overtime_approved"] == 5
    assert rec["totals"]["payroll_current"] == rec["totals"]["payroll_billed"]
    assert rec["summary_source"] == "none"


def test_reconciliation_flags_attendance_changed_after_billing(client):
    headers = _auth_header(client)
    client_id, employee_id = _seed(client, headers)
    _attendance(client, headers, employee_id, overtime=5, approve=True)
    _, invoice_id = _run_and_invoice(client, headers, client_id)

    # Absensi direvisi setelah invoice terbit: approval otomatis di-reset.
    _attendance(client, headers, employee_id, overtime=8, approve=False)

    kinds = {f["kind"] for f in _recon(client, headers, invoice_id)["findings"]}
    assert kinds == {"absensi_belum_disetujui", "lembur_beda"}


def test_reconciliation_flags_missing_attendance_and_total_drift(client, db_engine):
    headers = _auth_header(client)
    client_id, employee_id = _seed(client, headers)
    _, invoice_id = _run_and_invoice(client, headers, client_id)

    rec = _recon(client, headers, invoice_id)
    assert [f["kind"] for f in rec["findings"]] == ["tanpa_absensi"]
    assert rec["findings"][0]["employee_name"] == "Sari Wulandari"

    # Slip berubah setelah invoice terbit (mis. koreksi manual): total tidak lagi sama.
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE payslips SET gross = gross + 100000"))
    kinds = {f["kind"] for f in _recon(client, headers, invoice_id)["findings"]}
    assert "total_beda" in kinds


def test_reconciliation_requires_existing_invoice(client):
    headers = _auth_header(client)
    resp = client.get(
        "/api/v1/finance/invoices/00000000-0000-0000-0000-000000000000/reconciliation",
        headers=headers,
    )
    assert resp.status_code == 404


def test_reconciliation_ai_summary_is_labelled_and_never_alters_findings(client, monkeypatch):
    from app.modules.finance import reconciliation

    monkeypatch.setattr(reconciliation, "ai_configured", lambda: True)
    monkeypatch.setattr(
        reconciliation, "chat_completion", lambda *a, **k: "Cek absensi Sari sebelum kirim."
    )
    headers = _auth_header(client)
    client_id, _ = _seed(client, headers)
    _, invoice_id = _run_and_invoice(client, headers, client_id)

    rec = _recon(client, headers, invoice_id)
    assert rec["summary_source"] == "ai"
    assert rec["summary"] == "Cek absensi Sari sebelum kirim."
    assert [f["kind"] for f in rec["findings"]] == ["tanpa_absensi"]


def test_reconciliation_flags_approved_attendance_not_billed(client):
    headers = _auth_header(client)
    client_id, employee_id = _seed(client, headers)
    _attendance(client, headers, employee_id, overtime=0, approve=True)
    _, invoice_id = _run_and_invoice(client, headers, client_id)

    # Karyawan kedua klien yang sama baru masuk SETELAH run digenerate: absensinya
    # disetujui, tetapi tidak punya slip -> belum ikut ditagih.
    jo_id = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Operator 2", "headcount": 1},
    ).json()["id"]
    cand_id = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Rudi Hartono"}
    ).json()["id"]
    placement_id = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    ).json()["id"]
    late = client.post(
        "/api/v1/employees/onboard",
        headers=headers,
        json={"placement_id": placement_id, "base_salary": 4_000_000},
    ).json()["id"]
    _attendance(client, headers, late, overtime=0, approve=True)

    rec = _recon(client, headers, invoice_id)
    assert [(f["kind"], f["employee_name"]) for f in rec["findings"]] == [
        ("absensi_tidak_ditagih", "Rudi Hartono")
    ]
    assert rec["totals"]["headcount_billed"] == 1


def test_reconciliation_uses_project_run_of_the_invoiced_client(client):
    headers = _auth_header(client)
    client_id, employee_id = _seed(client, headers)
    _attendance(client, headers, employee_id, overtime=3, approve=True)
    run_id = client.post(
        "/api/v1/payroll/runs",
        headers=headers,
        json={"year": 2026, "month": 7, "run_type": "proyek", "client_id": client_id},
    ).json()["id"]
    resp = client.post(
        f"/api/v1/payroll/runs/{run_id}/generate", headers=headers, json={"overtime_rate": 50_000}
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 7, "run_id": run_id},
    )
    assert resp.status_code == 201, resp.text

    rec = _recon(client, headers, resp.json()["id"])
    assert rec["run_id"] == run_id
    # Total proyek = earnings + passthrough Saltab, dihitung dengan rumus yang sama
    # seperti saat invoice dibuat -> tidak ada "total_beda" palsu.
    assert rec["findings"] == [], rec["findings"]
    assert rec["totals"]["overtime_billed"] == 3


def test_generate_invoice_with_multiple_runs_in_period_picks_general_run(client):
    """Regresi: run internal + run proyek klien lain di periode yang sama dulu
    membuat generate invoice error 500 (MultipleResultsFound)."""
    headers = _auth_header(client)
    client_id, employee_id = _seed(client, headers)
    _attendance(client, headers, employee_id, overtime=0, approve=True)
    other = client.post("/api/v1/clients", headers=headers, json={"name": "PT Lain"}).json()["id"]
    internal = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 7}
    ).json()["id"]
    resp = client.post(f"/api/v1/payroll/runs/{internal}/generate", headers=headers, json={})
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=headers,
        json={"year": 2026, "month": 7, "run_type": "proyek", "client_id": other},
    )
    assert resp.status_code == 201, resp.text
    other_run = resp.json()["id"]

    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 7, "fee_amount": 0},
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    assert inv["payroll_run_id"] == internal
    assert inv["payroll_total"] > 0

    rec = _recon(client, headers, inv["id"])
    assert rec["run_id"] == internal
    assert rec["findings"] == [], rec["findings"]

    # Run proyek klien lain tidak boleh dipakai untuk menagih klien ini.
    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 8, "run_id": other_run},
    )
    assert resp.status_code == 422, resp.text
