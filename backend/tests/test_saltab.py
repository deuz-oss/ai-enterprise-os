"""Fase 9b — Saltab line-item, prorata absensi, BPJS dua sisi, invoice otomatis."""

from tests.conftest import _auth_header


def _setup_proyek_with_attendance(client, present_days=15):
    """Klien + placement + karyawan eksternal + rekap absensi tervalidasi."""
    admin = _auth_header(client)
    cl = client.post("/api/v1/clients", headers=admin, json={"name": "PT Saltab"}).json()
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=admin,
        json={"client_id": cl["id"], "title": "Admin Gudang", "headcount": 1},
    ).json()
    cand = client.post(
        "/api/v1/recruitment/candidates", headers=admin, json={"full_name": "TKO Saltab"}
    ).json()
    plc = client.post(
        "/api/v1/recruitment/placements",
        headers=admin,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"]},
    ).json()
    emp = client.post(
        "/api/v1/employees",
        headers=admin,
        json={
            "full_name": "TKO Saltab",
            "base_salary": 5_000_000,
            "placement_id": plc["id"],
        },
    ).json()

    att = client.post(
        "/api/v1/payroll/attendance",
        headers=admin,
        json={
            "employee_id": emp["id"],
            "year": 2026,
            "month": 6,
            "present_days": present_days,
        },
    ).json()
    client.patch(
        f"/api/v1/payroll/attendance/{att['id']}/client-approval",
        headers=admin,
        params={"approved": True},
    )
    return admin, cl["id"], emp


def test_saltab_components_prorata_and_bpjs(client):
    admin, _client_id, emp = _setup_proyek_with_attendance(client, present_days=11)

    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 6, "run_type": "proyek", "client_id": _client_id},
    ).json()
    gen = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate",
        headers=admin,
        json={"allowance": 1_000_000, "overtime_rate": 50_000, "prorata_absensi": True, "bpjs_enabled": True},
    )
    assert gen.status_code == 201, gen.text
    slip = gen.json()[0]

    saltab = client.get(f"/api/v1/payroll/runs/{run['id']}/saltab", headers=admin).json()
    row = next(r for r in saltab if r["payslip_id"] == slip["id"])
    codes = {c["code"]: c for c in row["components"]}

    # Prorata: Juni 2026 punya 22 hari kerja; hadir 11 → rasio 0.5
    assert codes["gaji_pokok"]["amount"] == 2_500_000
    assert codes["tunjangan"]["amount"] == 500_000
    assert "Prorata" in (codes["gaji_pokok"]["notes"] or "")
    # BPJS dua sisi muncul sebagai komponen
    assert "bpjs_kesehatan_py" in codes and codes["bpjs_kesehatan_py"]["ctype"] == "deduction"
    assert "jht_py" in codes and "jp_py" in codes
    assert codes["bpjs_employer"]["ctype"] == "passthrough"
    # PPh21 dihitung dari gross prorata
    expected_gross = 2_500_000 + 500_000
    assert float(slip["gross"]) == expected_gross

    # Override manual tunjangan → gross & net recompute
    comp_id = codes["tunjangan"]["id"]
    patched = client.patch(
        f"/api/v1/payroll/saltab/components/{comp_id}", headers=admin, json={"amount": 800_000}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["source"] == "manual"
    slips_now = client.get(f"/api/v1/payroll/runs/{run['id']}/slips", headers=admin).json()
    now = next(s for s in slips_now if s["id"] == slip["id"])
    assert float(now["gross"]) == 2_500_000 + 800_000 + float(slip["overtime_amount"])

    # CSV export tersedia
    csv_resp = client.get(f"/api/v1/payroll/runs/{run['id']}/saltab/export", headers=admin)
    assert csv_resp.status_code == 200
    assert "Gaji pokok" in csv_resp.text


def test_generate_tanpa_flag_bpjs_tidak_menambah_potongan(client):
    admin = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Tanpa BPJS Flag", "base_salary": 5_000_000}
    ).json()
    run = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 4}).json()
    slips = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={}).json()
    slip = next(s for s in slips if s["employee_id"] == emp["id"])
    # Default: tanpa BPJS, tanpa bank name → deductions 0
    assert float(slip["deductions"]) == 0
    assert float(slip["net_pay"]) == float(slip["gross"]) - float(slip["tax_pph21"])


def test_auto_invoice_draft_saat_client_approved(client):
    admin, client_id, emp = _setup_proyek_with_attendance(client, present_days=22)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 6, "run_type": "proyek", "client_id": client_id},
    ).json()
    client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate",
        headers=admin,
        json={"bpjs_enabled": True},
    )
    sub = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}).json()
    dec = client.post(
        f"/api/v1/payroll/client/{sub['raw_token']}/decision",
        json={"approved": True, "name": "Finance Klien"},
    )
    assert dec.status_code == 200

    invoices = client.get("/api/v1/finance/invoices", headers=admin).json()
    inv = next(i for i in invoices if i["client_id"] == client_id and i["month"] == 6)
    assert inv["status"] == "draft"
    assert inv["fee_amount"] == 0  # fee diatur Finance pada draft
    assert inv["payroll_total"] > 0  # earnings + passthrough BPJS employer
