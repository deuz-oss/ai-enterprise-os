from app.modules.payroll.tax import (
    TaxProfile,
    compute_pasal17_annual,
    compute_pasal17_monthly_average,
    compute_ter,
    ter_category,
)

from tests.conftest import _auth_header

# ---------- Mesin pajak (murni, tanpa API) ----------


def test_ptkp_annual():
    assert TaxProfile("tk", 0).ptkp_annual == 54_000_000
    assert TaxProfile("k", 0).ptkp_annual == 58_500_000
    assert TaxProfile("k", 2).ptkp_annual == 67_500_000
    # tanggungan dibatasi maksimal 3
    assert TaxProfile("k", 7).ptkp_annual == 72_000_000


def test_ter_category_mapping():
    assert ter_category(TaxProfile("tk", 0)) == "A"
    assert ter_category(TaxProfile("tk", 1)) == "A"
    assert ter_category(TaxProfile("k", 0)) == "A"
    assert ter_category(TaxProfile("tk", 3)) == "B"
    assert ter_category(TaxProfile("k", 1)) == "B"
    assert ter_category(TaxProfile("k", 3)) == "C"


def test_compute_ter_bracket_and_zero():
    # bruto rendah → 0% sesuai tabel TER A
    assert compute_ter(5_400_000, TaxProfile("tk", 0)) == 0
    # lapisan pertama non-nol TER A: >5.4jt s.d. 5.65jt = 0,25%
    assert compute_ter(5_650_000, TaxProfile("tk", 0)) == round(5_650_000 * 0.0025)
    # kategori C tarif puncak lebih rendah dari A pada bruto sangat besar
    big = 600_000_000
    assert compute_ter(big, TaxProfile("k", 3)) < compute_ter(big, TaxProfile("tk", 0))


def test_compute_pasal17_progressive():
    profile = TaxProfile("tk", 0)  # PTKP 54jt
    # PKP tepat di lapisan pertama: 60jt * 5%
    annual = 60_000_000 + 54_000_000
    assert compute_pasal17_annual(annual, profile) == 3_000_000
    # PKP nol karena di bawah PTKP
    assert compute_pasal17_annual(50_000_000, profile) == 0


def test_compute_pasal17_monthly_average():
    profile = TaxProfile("tk", 0)
    months = 12
    expected_annual = compute_pasal17_annual(10_000_000 * months, profile)
    monthly = compute_pasal17_monthly_average(10_000_000, months, profile)
    assert monthly == round(expected_annual / months)


# ---------- Alur payrol via API ----------


def _create_employee(client, headers, name="Payrol Karyawan", salary=6_000_000) -> dict:
    resp = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": name, "base_salary": salary},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_run(client, headers, year=2026, month=8) -> dict:
    resp = client.post("/api/v1/payroll/runs", headers=headers, json={"year": year, "month": month})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_attendance_upsert_and_client_approval(client):
    headers = _auth_header(client)
    emp = _create_employee(client, headers)

    created = client.post(
        "/api/v1/payroll/attendance",
        headers=headers,
        json={
            "employee_id": emp["id"],
            "year": 2026,
            "month": 8,
            "present_days": 22,
            "overtime_hours": 10,
        },
    )
    assert created.status_code == 201, created.text

    approved = client.patch(
        f"/api/v1/payroll/attendance/{created.json()['id']}/client-approval",
        headers=headers,
        params={"approved": True},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["client_approved"] is True
    assert body["approved_at"] is not None

    # edit ulang me-reset approval
    updated = client.post(
        "/api/v1/payroll/attendance",
        headers=headers,
        json={"employee_id": emp["id"], "year": 2026, "month": 8, "overtime_hours": 12},
    )
    assert updated.status_code == 201
    assert updated.json()["client_approved"] is False


def test_generate_slips_requires_client_approval_for_overtime(client):
    headers = _auth_header(client)
    emp = _create_employee(client, headers, salary=6_000_000)
    run = _create_run(client, headers)

    # lembur TANPA approval klien → tidak boleh masuk slip
    client.post(
        "/api/v1/payroll/attendance",
        headers=headers,
        json={"employee_id": emp["id"], "year": 2026, "month": 8, "overtime_hours": 10},
    )
    slips = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate",
        headers=headers,
        json={"allowance": 500_000, "overtime_rate": 50_000},
    )
    assert slips.status_code == 201
    first = slips.json()[0]
    assert first["overtime_hours"] == 0
    assert first["gross"] == 6_500_000

    # setelah approval klien, generate ulang menambahkan lembur
    attendance = client.get(
        "/api/v1/payroll/attendance", headers=headers, params={"year": 2026, "month": 8}
    ).json()
    client.patch(
        f"/api/v1/payroll/attendance/{attendance[0]['id']}/client-approval",
        headers=headers,
        params={"approved": True},
    )
    slips2 = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate",
        headers=headers,
        json={"allowance": 500_000, "overtime_rate": 50_000},
    )
    # slip sudah ada untuk karyawan ini → duplikat ditolak; buat run baru untuk uji lembur
    assert slips2.status_code == 409

    run2 = _create_run(client, headers, year=2026, month=9)
    client.post(
        "/api/v1/payroll/attendance",
        headers=headers,
        json={"employee_id": emp["id"], "year": 2026, "month": 9, "overtime_hours": 10},
    )
    att_sep = client.get(
        "/api/v1/payroll/attendance", headers=headers, params={"year": 2026, "month": 9}
    ).json()[0]
    client.patch(
        f"/api/v1/payroll/attendance/{att_sep['id']}/client-approval",
        headers=headers,
        params={"approved": True},
    )
    slips3 = client.post(
        f"/api/v1/payroll/runs/{run2['id']}/generate",
        headers=headers,
        json={"allowance": 500_000, "overtime_rate": 50_000},
    ).json()
    assert slips3[0]["overtime_hours"] == 10
    assert slips3[0]["overtime_amount"] == 500_000
    gross = 6_500_000 + 500_000
    assert float(slips3[0]["gross"]) == gross
    assert float(slips3[0]["net_pay"]) == gross - float(slips3[0]["tax_pph21"])


def test_finalize_run_locks(client):
    headers = _auth_header(client)
    _create_employee(client, headers)
    run = _create_run(client, headers)

    empty = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=headers)
    assert empty.status_code == 422  # belum ada slip

    client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={}
    )
    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=headers)
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "final"

    again = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={}
    )
    assert again.status_code == 409  # run final terkunci


def test_duplicate_run_rejected(client):
    headers = _auth_header(client)
    _create_run(client, headers, year=2026, month=7)
    dup = client.post("/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 7})
    assert dup.status_code == 409


def test_tax_preview_endpoint(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/payroll/tax-preview",
        headers=headers,
        json={"gross_monthly": 5_000_000, "marital_status": "tk", "dependents": 0},
    )
    assert resp.status_code == 200
    assert resp.json()["tax_pph21"] == 0  # di bawah ambang TER A pertama
