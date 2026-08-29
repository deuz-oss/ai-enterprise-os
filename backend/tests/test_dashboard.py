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
