from datetime import date, timedelta

from tests.conftest import _auth_header


def _seed_client_with_payroll(client, headers, name="PT Tagihan Jaya", salary=5_000_000):
    """Buat klien → JO → kandidat → placement → karyawan + payrol run berisi slip."""
    resp = client.post("/api/v1/clients", headers=headers, json={"name": name})
    client_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Staff", "headcount": 1},
    )
    jo_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/recruitment/candidates", headers=headers, json={"full_name": "Fajar Nugroho"}
    )
    cand_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    placement_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/employees/onboard",
        headers=headers,
        json={"placement_id": placement_id, "base_salary": salary},
    )
    assert resp.status_code == 201, resp.text
    # onboard tidak membawa base_salary; set manual via PATCH
    resp = client.patch(
        f"/api/v1/employees/{resp.json()['id']}",
        headers=headers,
        json={"base_salary": salary},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 6}
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/payroll/runs/{run_id}/generate", headers=headers, json={}
    )
    assert resp.status_code == 201, resp.text
    return client_id, run_id


def test_generate_invoice_from_payroll(client):
    headers = _auth_header(client)
    client_id, _ = _seed_client_with_payroll(client, headers)

    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={
            "client_id": client_id,
            "year": 2026,
            "month": 6,
            "fee_amount": 2_000_000,
        },
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    assert inv["invoice_no"].startswith("INV/")
    assert float(inv["payroll_total"]) > 0

    subtotal = float(inv["payroll_total"]) + 2_000_000
    ppn = round(subtotal * float(inv["ppn_rate"]))
    pph23 = round(2_000_000 * float(inv["pph23_rate"]))
    assert float(inv["ppn_amount"]) == ppn
    assert float(inv["pph23_amount"]) == pph23
    assert float(inv["total_due"]) == subtotal + ppn - pph23

    dup = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 6, "fee_amount": 0},
    )
    assert dup.status_code == 409


def test_generate_invoice_without_payroll_rejected(client):
    headers = _auth_header(client)
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT Kosong"})
    client_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2030, "month": 1, "fee_amount": 1000000},
    )
    assert resp.status_code == 422


def test_invoice_paid_and_aging(client):
    headers = _auth_header(client)
    client_id, _ = _seed_client_with_payroll(client, headers, name="PT Telat Bayar")
    resp = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 6, "fee_amount": 500_000},
    )
    invoice = resp.json()

    # belum lewat jatuh tempo → aging kosong
    empty = client.get("/api/v1/finance/invoices/aging", headers=headers).json()
    assert len(empty) == 0

    # mundurkan jatuh tempo 45 hari → masuk bucket 31-60
    overdue_date = (date.today() - timedelta(days=45)).isoformat()
    updated = client.patch(
        f"/api/v1/finance/invoices/{invoice['id']}",
        headers=headers,
        json={"status": "terkirim", "due_date": overdue_date},
    )
    assert updated.status_code == 200
    aging = client.get("/api/v1/finance/invoices/aging", headers=headers).json()
    assert len(aging) == 1
    assert aging[0]["bucket"] == "31-60"
    assert aging[0]["client_name"] == "PT Telat Bayar"

    # tandai dibayar → keluar dari aging, paid_at terisi
    paid = client.patch(
        f"/api/v1/finance/invoices/{invoice['id']}",
        headers=headers,
        json={"status": "dibayar"},
    )
    assert paid.status_code == 200
    assert paid.json()["paid_at"] is not None
    assert client.get("/api/v1/finance/invoices/aging", headers=headers).json() == []

    # invoice lunas tidak boleh diubah statusnya lagi
    reopen = client.patch(
        f"/api/v1/finance/invoices/{invoice['id']}",
        headers=headers,
        json={"status": "draft"},
    )
    assert reopen.status_code == 409


def test_cashflow_crud_and_summary(client):
    headers = _auth_header(client)
    client.post(
        "/api/v1/finance/cashflow",
        headers=headers,
        json={
            "direction": "masuk",
            "category": "pembayaran_klien",
            "amount": 10_000_000,
            "entry_date": "2026-07-05",
        },
    )
    client.post(
        "/api/v1/finance/cashflow",
        headers=headers,
        json={
            "direction": "keluar",
            "category": "gaji_karyawan",
            "amount": 6_000_000,
            "entry_date": "2026-07-28",
        },
    )
    summary = client.get(
        "/api/v1/finance/cashflow/summary", headers=headers, params={"year": 2026, "month": 7}
    ).json()
    assert summary["inflow"] == 10_000_000
    assert summary["outflow"] == 6_000_000
    assert summary["net"] == 4_000_000

    entries = client.get(
        "/api/v1/finance/cashflow", headers=headers, params={"year": 2026}
    ).json()
    assert len(entries) == 2
