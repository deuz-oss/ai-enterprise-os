"""Isolasi tenant untuk SEMUA endpoint baru siklus audit 2026-10-08 (cek semua gap).

Tenant A membuat data; admin tenant B mencoba membaca & MEMAKAI ID milik A
lewat URL maupun payload. Semua harus gagal tanpa efek samping di A.
"""

from datetime import date
from io import BytesIO

import pytest

from tests.conftest import _auth_header, _login_header, _platform_admin_header
from tests.test_apps import _provision_tenant, _seed_active_subscription
from tests.test_invoice_reconciliation import _run_and_invoice, _seed


@pytest.fixture()
def two_tenants(client):
    a = _auth_header(client)
    client_id, _ = _seed(client, a)
    run_id, invoice_id = _run_and_invoice(client, a, client_id)
    client.patch(f"/api/v1/finance/invoices/{invoice_id}", headers=a, json={"status": "terkirim"})
    accounts = {
        x["code"]: x["id"] for x in client.get("/api/v1/accounting/accounts", headers=a).json()
    }
    bill = client.post(
        "/api/v1/accounting/purchases",
        headers=a,
        json={"vendor_name": "CV A", "expense_account_id": accounts["5-9000"], "amount": 750_000},
    ).json()
    lead = client.post("/api/v1/leads", headers=a, json={"company_name": "Lead A"}).json()
    tmpl = client.post(
        "/api/v1/quotation-templates",
        headers=a,
        json={
            "name": "T A",
            "field_schema": [{"key": "g", "label": "Gaji", "role": "base_salary"}],
        },
    ).json()
    quotation = client.post(
        "/api/v1/quotations",
        headers=a,
        json={"lead_id": lead["id"], "template_id": tmpl["id"], "field_values": {"g": "5000000"}},
    ).json()
    body = f"tanggal;keterangan;mutasi_masuk;mutasi_keluar\n{date.today()};MUTASI A;999000;0\n"
    client.post(
        "/api/v1/accounting/cashbank/statement/import",
        headers=a,
        files={"file": ("a.csv", BytesIO(body.encode()), "text/csv")},
    )
    a_line = client.get("/api/v1/accounting/cashbank/statement", headers=a).json()[0]

    platform = _platform_admin_header(client)
    tenant_b = _provision_tenant(client, platform, "tenant-b")
    tenant_b_id = tenant_b.get("id") or tenant_b.get("tenant", {}).get("id")
    _seed_active_subscription(client, tenant_b_id)
    b = _login_header(client, "admin-tenant-b@example.com", "rahasia-123")
    b_accounts = {
        x["code"]: x["id"] for x in client.get("/api/v1/accounting/accounts", headers=b).json()
    }
    return {
        "a": a,
        "b": b,
        "invoice_id": invoice_id,
        "run_id": run_id,
        "bill_id": bill["id"],
        "template_id": tmpl["id"],
        "quotation_id": quotation["id"],
        "a_line_id": a_line["id"],
        "a_accounts": accounts,
        "b_accounts": b_accounts,
    }


def test_read_endpoints_do_not_leak_other_tenant(client, two_tenants):
    t = two_tenants
    b = t["b"]
    for method, url in [
        ("get", f"/api/v1/finance/invoices/{t['invoice_id']}/reconciliation"),
        ("post", f"/api/v1/finance/invoices/{t['invoice_id']}/reminder-draft"),
        ("get", f"/api/v1/payroll/runs/{t['run_id']}/review"),
        ("get", f"/api/v1/quotations/{t['quotation_id']}/pricing-check"),
        ("get", f"/api/v1/accounting/cashbank/statement/{t['a_line_id']}/suggestions"),
    ]:
        resp = getattr(client, method)(url, headers=b)
        assert resp.status_code == 404, (url, resp.status_code, resp.text)

    resp = client.post(
        "/api/v1/quotations/pricing-check",
        headers=b,
        json={"template_id": t["template_id"], "field_values": {"g": "1"}},
    )
    assert resp.status_code == 404, resp.text

    digest = client.get("/api/v1/employees/compliance-digest", headers=b).json()
    assert sum(digest["counts"].values()) == 0
    assert client.get("/api/v1/overview/anomalies", headers=b).json()["items"] == []


def test_payload_ids_of_other_tenant_cannot_be_used(client, two_tenants):
    t = two_tenants
    b = t["b"]
    body = f"tanggal;keterangan;mutasi_masuk;mutasi_keluar\n{date.today()};MUTASI B;750000;0\n"
    client.post(
        "/api/v1/accounting/cashbank/statement/import",
        headers=b,
        files={"file": ("b.csv", BytesIO(body.encode()), "text/csv")},
    )
    b_line = client.get("/api/v1/accounting/cashbank/statement", headers=b).json()[0]
    apply_url = f"/api/v1/accounting/cashbank/statement/{b_line['id']}/apply"
    # Kontrol positif: B BISA memakai endpoint yang sama untuk datanya sendiri,
    # jadi 404/422 di bawah memang karena ID milik A, bukan karena B tak punya akses.
    own = client.get(f"/api/v1/accounting/cashbank/statement/{b_line['id']}/suggestions", headers=b)
    assert own.status_code == 200, own.text

    attempts = [
        {"kind": "settle_invoice", "invoice_id": t["invoice_id"]},
        {"kind": "pay_bill", "bill_id": t["bill_id"], "bank_account_id": t["b_accounts"]["1-1100"]},
        {
            "kind": "create_transaction",
            "bank_account_id": t["a_accounts"]["1-1100"],  # rekening milik A
        },
    ]
    for payload in attempts:
        resp = client.post(apply_url, headers=b, json=payload)
        assert resp.status_code in (404, 422), (payload, resp.status_code, resp.text)

    # Data A tidak berubah.
    a = t["a"]
    invoice = client.get(f"/api/v1/finance/invoices/{t['invoice_id']}", headers=a).json()
    assert invoice["status"] == "terkirim"
    bills = client.get("/api/v1/accounting/purchases", headers=a).json()
    assert bills[0]["status"] != "dibayar"
    a_line = client.get("/api/v1/accounting/cashbank/statement", headers=a).json()[0]
    assert a_line["status"] != "tercocok"


def test_nav_query_does_not_resolve_other_tenant_client(client, two_tenants, monkeypatch):
    import app.core.llm as llm

    monkeypatch.setattr(llm, "ai_configured", lambda: True)
    monkeypatch.setattr(
        llm,
        "chat_completion",
        lambda *a, **k: {"page": "employees", "client": "PT Rekon Absensi"},  # klien A
    )
    out = client.post(
        "/api/v1/ai/nav-query", headers=two_tenants["b"], json={"text": "karyawan PT Rekon"}
    ).json()
    assert out["applied"] == [] and any("tidak ditemukan" in i for i in out["ignored"])
