from datetime import datetime, timedelta

from tests.conftest import _auth_header
from tests.test_finance import _seed_client_with_payroll


def test_overview_revenue_mtd_counts_only_paid_invoices_this_month(client):
    """Dashboard §8 widget 1/7 `finance.revenue_mtd` — sebelumnya dideklarasikan
    tapi tidak pernah dihitung (selalu 0). Regresi: hanya invoice berstatus
    `dibayar` yang lunas bulan berjalan yang dihitung, bukan sekadar `terkirim`."""
    headers = _auth_header(client)
    client_id, _ = _seed_client_with_payroll(client, headers, name="PT Revenue MTD")

    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 6, "fee_amount": 500_000},
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()

    before = client.get("/api/v1/overview", headers=headers).json()
    assert before["finance"]["revenue_mtd"] == 0
    assert before["finance"]["invoices_total"] == 1

    sent = client.patch(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=headers, json={"status": "terkirim"}
    )
    assert sent.status_code == 200
    still_zero = client.get("/api/v1/overview", headers=headers).json()
    assert still_zero["finance"]["revenue_mtd"] == 0  # terkirim belum lunas

    paid = client.patch(
        f"/api/v1/finance/invoices/{invoice['id']}", headers=headers, json={"status": "dibayar"}
    )
    assert paid.status_code == 200
    after = client.get("/api/v1/overview", headers=headers).json()
    assert after["finance"]["revenue_mtd"] == paid.json()["total_due"]


def test_overview_widget3_job_order_stage_and_interviews_this_week(client):
    """Dashboard §8 widget 3 — Recruitment & Talent: JO progress bar + interview minggu ini."""
    headers = _auth_header(client)
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT Widget3"})
    client_id = resp.json()["id"]
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Staff Gudang", "headcount": 1},
    ).json()
    cand = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Widget3 Test"}
    ).json()

    before = client.get("/api/v1/overview", headers=headers).json()
    assert before["recruitment_talent"]["job_orders_by_stage"]["open"] == 1
    assert before["recruitment_talent"]["interviews_this_week"] == 0

    soon = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
    far = (datetime.now() + timedelta(days=20)).replace(microsecond=0).isoformat()
    created = client.post(
        "/api/v1/recruitment/interviews",
        headers=headers,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"], "scheduled_at": soon},
    )
    assert created.status_code == 201, created.text
    client.post(
        "/api/v1/recruitment/interviews",
        headers=headers,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"], "scheduled_at": far},
    )

    after = client.get("/api/v1/overview", headers=headers).json()
    assert after["recruitment_talent"]["interviews_this_week"] == 1  # hanya yang ≤7 hari


def test_overview_widget5_active_placements_by_client(client):
    """Dashboard §8 widget 5 — Operations & Projects: placement aktif per klien."""
    headers = _auth_header(client)
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT Widget5"})
    client_id = resp.json()["id"]
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Staff Gudang", "headcount": 2},
    ).json()
    cand = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Widget5 Test"}
    ).json()
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"]},
    ).json()

    before = client.get("/api/v1/overview", headers=headers).json()
    assert before["operations"]["active_placements_by_client"] == []  # belum onboarded
    assert isinstance(before["operations"]["profit_by_client"], list)

    onboarded = client.patch(
        f"/api/v1/recruitment/placements/{placement['id']}",
        headers=headers,
        json={"status": "onboarded"},
    )
    assert onboarded.status_code == 200, onboarded.text

    after = client.get("/api/v1/overview", headers=headers).json()
    assert after["operations"]["active_placements_by_client"] == [
        {"client": "PT Widget5", "active_placements": 1}
    ]


def test_overview_people_bpjs_and_insurance_complete(client):
    """Dashboard §8 widget "People & Compliance" — bpjs_complete/insurance_complete.

    Regresi: insurance_complete sebelumnya menghitung kolom lama
    `Employee.insurance_policy_no` (PRD v2.0) yang sudah tidak pernah diisi
    UI — polis asuransi sekarang disimpan di tabel one-to-many
    `EmployeeInsurance` (PRD v3.0). Widget selalu 0% walau polis sungguhan
    sudah dibuat lewat `/employees/{id}/insurances`."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Widget People Test"}
    ).json()

    before = client.get("/api/v1/overview", headers=headers).json()
    assert before["people"]["bpjs_complete"] == 0
    assert before["people"]["insurance_complete"] == 0

    bpjs = client.patch(
        f"/api/v1/employees/{emp['id']}",
        headers=headers,
        json={"bpjs_kesehatan_no": "0001234567890"},
    )
    assert bpjs.status_code == 200, bpjs.text

    ins = client.post(
        f"/api/v1/employees/{emp['id']}/insurances",
        headers=headers,
        json={"provider": "prudential", "policy_no": "POL-1"},
    )
    assert ins.status_code == 201, ins.text

    after = client.get("/api/v1/overview", headers=headers).json()
    assert after["people"]["bpjs_complete"] == 1
    assert after["people"]["insurance_complete"] == 1


def test_overview_payroll_summary_maps_real_status_values(client):
    """Dashboard widget "Payroll Run" — bucket draft/submitted/approved/finalized.

    Regresi: dict lama diisi pakai key literal "submitted"/"approved"/
    "finalized" yang TIDAK PERNAH cocok dengan value asli
    `PayrollRunStatus` (submitted_to_client/client_approved/final) — jadi
    breakdown selalu 0 walau ada run yang sudah final."""
    headers = _auth_header(client)
    client.post("/api/v1/employees", headers=headers, json={"full_name": "Dashboard Payroll Test"})

    run = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 5}
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={})
    client.post(f"/api/v1/payroll/runs/{run['id']}/start-processing", headers=headers)
    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=headers)
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "final"

    data = client.get("/api/v1/overview", headers=headers).json()
    assert data["payroll"]["finalized"] == 1
    assert data["payroll"]["draft"] == 0
