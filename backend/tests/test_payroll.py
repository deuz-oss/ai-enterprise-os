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


def test_bukti_potong_pdf_per_karyawan(client):
    """PRD v3.0 §6 — dokumen compliance yang sebelumnya belum ada sama sekali."""
    headers = _auth_header(client)
    emp = _create_employee(client, headers, name="Bukti Potong Karyawan", salary=8_000_000)
    run = _create_run(client, headers, year=2026, month=9)

    generated = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert generated.status_code == 201, generated.text

    pdf = client.get(
        f"/api/v1/payroll/runs/{run['id']}/bukti-potong/{emp['id']}/pdf", headers=headers
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"
    assert "1.1-202609-0001" in pdf.headers["content-disposition"]

    # Karyawan yang tidak punya slip di run ini -> 404, bukan PDF kosong.
    other = _create_employee(client, headers, name="Bukan Peserta Run Ini")
    missing = client.get(
        f"/api/v1/payroll/runs/{run['id']}/bukti-potong/{other['id']}/pdf", headers=headers
    )
    assert missing.status_code == 404


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

    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=headers)
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "final"

    again = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
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


def test_send_saltab_to_client_email(client):
    """Fase 23 butir 4 -- tombol kirim manual, email penerima diisi manual."""
    from unittest.mock import patch

    headers = _auth_header(client)
    _create_employee(client, headers, name="Saltab Karyawan")
    run = _create_run(client, headers, year=2026, month=10)
    generated = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert generated.status_code == 201, generated.text

    with patch("app.modules.notifications.service.send_raw_email_with_attachment") as send:
        resp = client.post(
            f"/api/v1/payroll/runs/{run['id']}/send-to-client",
            headers=headers,
            json={"recipient_email": "klien@contoh.co.id"},
        )
        assert resp.status_code == 204, resp.text
        assert send.call_count == 1
        args, kwargs = send.call_args
        assert args[0] == "klien@contoh.co.id"
        assert kwargs["attachment_bytes"][:4] == b"%PDF"

    missing_email = client.post(
        f"/api/v1/payroll/runs/{run['id']}/send-to-client", headers=headers, json={}
    )
    assert missing_email.status_code == 422


def test_payroll_lock_skips_employee_in_generate_slips(client):
    """Fase 26 butir 4 -- karyawan payroll_locked dilewati saat generate slip."""
    headers = _auth_header(client)
    locked_emp = _create_employee(client, headers, name="Terkunci")
    free_emp = _create_employee(client, headers, name="Bebas")

    lock = client.post(f"/api/v1/employees/{locked_emp['id']}/payroll-lock", headers=headers)
    assert lock.status_code == 200, lock.text

    run = _create_run(client, headers, year=2026, month=11)
    generated = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert generated.status_code == 201, generated.text

    slips = client.get(f"/api/v1/payroll/runs/{run['id']}/slips", headers=headers).json()
    employee_ids = {s["employee_id"] for s in slips}
    assert free_emp["id"] in employee_ids
    assert locked_emp["id"] not in employee_ids


def test_payroll_lock_blocks_saltab_component_edit(client):
    """Fase 26 butir 4 -- setelah dikunci, edit grid Saltab karyawan tsb ditolak."""
    headers = _auth_header(client)
    emp = _create_employee(client, headers, name="Rina Payroll")
    run = _create_run(client, headers, year=2026, month=12)
    generated = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert generated.status_code == 201, generated.text

    saltab = client.get(f"/api/v1/payroll/runs/{run['id']}/saltab", headers=headers).json()
    component_id = saltab[0]["components"][0]["id"]

    lock = client.post(f"/api/v1/employees/{emp['id']}/payroll-lock", headers=headers)
    assert lock.status_code == 200

    edit = client.patch(
        f"/api/v1/payroll/saltab/components/{component_id}",
        headers=headers,
        json={"amount": 1_000_000},
    )
    assert edit.status_code == 409, edit.text


def test_send_payslip_email_to_employee(client):
    """Fase 26 butir 5 -- payslip dikirim ke email karyawan sendiri, terpisah
    dari alur Ops->klien (Fase 23)."""
    from unittest.mock import patch

    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    headers = _auth_header(client)
    emp = _create_employee(client, headers, name="Sinta Payslip")

    db = client.testing_session()
    try:
        user = create_user(
            db,
            UserCreate(
                email="sinta-payslip@outsourcing.co.id",
                full_name="Sinta",
                password="rahasia-123",
                role="karyawan",
            ),
        )
        user_id = str(user.id)
    finally:
        db.close()

    linked = client.patch(
        f"/api/v1/employees/{emp['id']}", headers=headers, json={"user_id": user_id}
    )
    assert linked.status_code == 200, linked.text

    run = _create_run(client, headers, year=2027, month=1)
    generated = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert generated.status_code == 201, generated.text

    with patch("app.modules.notifications.service.send_raw_email_with_attachment") as send:
        resp = client.post(
            f"/api/v1/payroll/runs/{run['id']}/employees/{emp['id']}/send-payslip-email",
            headers=headers,
        )
        assert resp.status_code == 204, resp.text
        assert send.call_count == 1
        args, kwargs = send.call_args
        assert args[0] == "sinta-payslip@outsourcing.co.id"
        assert kwargs["attachment_bytes"][:4] == b"%PDF"


def test_send_payslip_email_requires_linked_account(client):
    headers = _auth_header(client)
    emp = _create_employee(client, headers, name="Tono Belum Tertaut")
    run = _create_run(client, headers, year=2027, month=2)
    generated = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    assert generated.status_code == 201, generated.text

    resp = client.post(
        f"/api/v1/payroll/runs/{run['id']}/employees/{emp['id']}/send-payslip-email",
        headers=headers,
    )
    assert resp.status_code == 400
