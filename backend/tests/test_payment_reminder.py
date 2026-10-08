"""Draf pengingat pembayaran (audit 2026-10-08 Phase 6, collection assistant)."""

from datetime import date, timedelta

from tests.conftest import _auth_header
from tests.test_finance import _seed_client_with_payroll


def _overdue_invoice(client, headers, status="terkirim"):
    client_id, _ = _seed_client_with_payroll(client, headers, name="PT Pengingat")
    client.patch(
        f"/api/v1/clients/{client_id}",
        headers=headers,
        json={"pic_name": "Rina", "pic_email": "rina@example.com"},
    )
    inv = client.post(
        "/api/v1/finance/invoices/generate",
        headers=headers,
        json={"client_id": client_id, "year": 2026, "month": 6, "fee_amount": 500_000},
    ).json()
    due = (date.today() - timedelta(days=12)).isoformat()
    resp = client.patch(
        f"/api/v1/finance/invoices/{inv['id']}",
        headers=headers,
        json={"status": status, "due_date": due},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_draf_template_memuat_fakta_invoice(client):
    headers = _auth_header(client)
    inv = _overdue_invoice(client, headers)
    resp = client.post(f"/api/v1/finance/invoices/{inv['id']}/reminder-draft", headers=headers)
    assert resp.status_code == 200, resp.text
    draft = resp.json()
    assert draft["source"] == "template"
    assert draft["days_overdue"] == 12
    assert inv["invoice_no"] in draft["body"]
    assert "Rina" in draft["body"]
    assert draft["to"] == "rina@example.com"


def test_draf_ditolak_untuk_invoice_draft(client):
    headers = _auth_header(client)
    inv = _overdue_invoice(client, headers, status="draft")
    resp = client.post(f"/api/v1/finance/invoices/{inv['id']}/reminder-draft", headers=headers)
    assert resp.status_code == 422


def test_draf_ai_tanpa_nomor_invoice_jatuh_ke_template(client, monkeypatch):
    import app.modules.finance.reminder as reminder

    monkeypatch.setattr(reminder, "ai_configured", lambda: True)
    monkeypatch.setattr(
        reminder,
        "chat_completion",
        lambda *a, **k: {"subject": "Halo", "body": "Mohon segera bayar Rp 99.999.999."},
    )
    headers = _auth_header(client)
    inv = _overdue_invoice(client, headers)
    draft = client.post(
        f"/api/v1/finance/invoices/{inv['id']}/reminder-draft", headers=headers
    ).json()
    assert draft["source"] == "template"
    assert "99.999.999" not in draft["body"]


def test_draf_ai_valid_dipakai(client, monkeypatch):
    import app.modules.finance.reminder as reminder
    from app.core.money import format_rupiah

    headers = _auth_header(client)
    inv = _overdue_invoice(client, headers)
    amount = format_rupiah(inv["total_due"])
    monkeypatch.setattr(reminder, "ai_configured", lambda: True)
    monkeypatch.setattr(
        reminder,
        "chat_completion",
        lambda *a, **k: {
            "subject": f"Pengingat {inv['invoice_no']}",
            "body": f"Invoice {inv['invoice_no']} sebesar {amount} sudah lewat jatuh tempo.",
        },
    )
    draft = client.post(
        f"/api/v1/finance/invoices/{inv['id']}/reminder-draft", headers=headers
    ).json()
    assert draft["source"] == "ai"
    assert amount in draft["body"]
