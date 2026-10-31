"""Fase 28 lanjutan: kwitansi resmi PDF (rencana §13 kasus 29-36)."""

import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from tests.billing_support import (  # noqa: F401 - fixture
    billing_env,
    run_in_tenant,
    setup_tenant,
    webhook,
)
from tests.test_billing import _default_tenant_id, _set_commercial


def _subscribe_and_pay(client, admin, tier: str = "tier1") -> dict:
    resp = client.post("/api/v1/billing/subscribe", headers=admin, json={"tier": tier})
    assert resp.status_code == 200, resp.text
    invoice_id = resp.json()["checkout_url"].split("/")[3]
    paid = webhook(client, {"id": invoice_id, "status": "PAID", "payment_channel": "BCA"})
    assert paid.status_code == 200, paid.text
    return resp.json()


def _issue(client, tenant_id: str, issued_at: datetime):
    from app.modules.billing import receipts
    from app.modules.billing.models import PaymentIntent, PaymentIntentType

    def _apply(db):
        intent = PaymentIntent(
            tenant_id=UUID(tenant_id),
            type=PaymentIntentType.topup,
            amount=10_000,
            provider_invoice_id=f"sbx-manual-{issued_at.timestamp()}",
        )
        db.add(intent)
        db.flush()
        r = receipts.issue_receipt(
            db,
            tenant_id=UUID(tenant_id),
            lines=[{"description": "x", "qty": 1, "unit_price": "10000", "amount": "10000"}],
            total=Decimal(10_000),
            payment_method_label="Test",
            provider_reference=None,
            issued_at=issued_at,
            intent=intent,
        )
        db.commit()
        return r.receipt_number

    return run_in_tenant(client, tenant_id, _apply)


def test_aktivasi_menerbitkan_kwitansi_bernomor_urut(client, billing_env):  # noqa: F811
    """#29 kwitansi pertama 000001, berikutnya 000002 (urut global)."""
    admin = setup_tenant(client)[0]
    _subscribe_and_pay(client, admin)
    rows = client.get("/api/v1/billing/receipts", headers=admin).json()
    year = datetime.now(UTC).year
    assert len(rows) == 1
    assert rows[0]["receipt_number"] == f"AEOS/KW/{year}/000001"
    assert rows[0]["total"] == 500_000
    assert rows[0]["payment_method_label"] == "Invoice Xendit (BCA)"
    _subscribe_and_pay(client, admin, "tier2")
    numbers = [
        r["receipt_number"] for r in client.get("/api/v1/billing/receipts", headers=admin).json()
    ]
    assert f"AEOS/KW/{year}/000002" in numbers
    txs = client.get("/api/v1/billing/transactions", headers=admin).json()
    assert any(t["receipt_id"] for t in txs if t["type"] == "subscription_charge")


def test_penomoran_reset_per_tahun(client, billing_env):  # noqa: F811
    """#30 tahun baru -> nomor kembali 000001."""
    _, tenant_id = setup_tenant(client)
    n1 = _issue(client, tenant_id, datetime(2031, 12, 31, 10, 0, tzinfo=UTC))
    n2 = _issue(client, tenant_id, datetime(2032, 1, 2, 10, 0, tzinfo=UTC))
    assert n1 == "AEOS/KW/2031/000001"
    assert n2 == "AEOS/KW/2032/000001"


def test_webhook_ulang_tidak_menerbitkan_kwitansi_kedua(client, billing_env):  # noqa: F811
    """#31"""
    admin = setup_tenant(client)[0]
    resp = client.post("/api/v1/billing/topup", headers=admin, json={"amount": 50_000})
    invoice_id = resp.json()["checkout_url"].split("/")[3]
    webhook(client, {"id": invoice_id, "status": "PAID"})
    webhook(client, {"id": invoice_id, "status": "PAID"}, headers={"webhook-id": "lain"})
    assert len(client.get("/api/v1/billing/receipts", headers=admin).json()) == 1


def test_pdf_dirender_sekali_dan_immutable(client, billing_env, monkeypatch):  # noqa: F811
    """#32 + #33 + #36 render pertama menyimpan objek; unduhan kedua identik
    tanpa render ulang; snapshot pembeli tidak berubah setelah profil diubah."""
    from app.modules.billing import receipts
    from pypdf import PdfReader

    admin = setup_tenant(client)[0]
    client.put(
        "/api/v1/billing/profile",
        headers=admin,
        json={"legal_name": "PT Klien Lama", "npwp": "0123456789012345"},
    )
    _subscribe_and_pay(client, admin)
    receipt_id = client.get("/api/v1/billing/receipts", headers=admin).json()[0]["id"]
    client.put("/api/v1/billing/profile", headers=admin, json={"legal_name": "PT Klien Baru"})

    calls: list[int] = []
    original = receipts._render_pdf

    def _counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(receipts, "_render_pdf", _counting)
    first = client.get(f"/api/v1/billing/receipts/{receipt_id}/pdf", headers=admin)
    assert first.status_code == 200, first.text
    assert first.headers["content-type"] == "application/pdf"
    second = client.get(f"/api/v1/billing/receipts/{receipt_id}/pdf", headers=admin)
    assert first.content == second.content
    assert len(calls) == 1

    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(first.content)).pages)
    assert "KWITANSI" in text
    assert "AEOS/KW/" in text
    assert "PT Aeos Teknologi" in text
    assert "PT Klien Lama" in text and "PT Klien Baru" not in text
    assert "Rp500.000" in text


def test_ppn_hanya_bila_pkp(client, billing_env, monkeypatch):  # noqa: F811
    """#34 non-PKP -> PPN 0; PKP + tarif -> DPP/PPN (harga termasuk PPN)."""
    from app.modules.billing.models import BillingReceipt

    _, tenant_id = setup_tenant(client)
    _issue(client, tenant_id, datetime.now(UTC))
    monkeypatch.setattr(billing_env, "aeos_seller_is_pkp", True)
    monkeypatch.setattr(billing_env, "billing_ppn_rate", Decimal("0.11"))
    _issue(client, tenant_id, datetime.now(UTC))
    rows = run_in_tenant(
        client,
        tenant_id,
        lambda db: list(
            db.execute(select(BillingReceipt).order_by(BillingReceipt.sequence_no)).scalars()
        ),
    )
    assert rows[0].ppn_amount == 0 and rows[0].dpp == rows[0].total
    assert rows[1].dpp == Decimal("9009")  # 10000 / 1.11 dibulatkan
    assert rows[1].ppn_amount == Decimal("991")
    assert rows[1].dpp + rows[1].ppn_amount == rows[1].total


def test_isolasi_tenant_kwitansi(client, billing_env):  # noqa: F811
    """#35"""
    from tests.conftest import _login_header, _platform_admin_header

    admin = setup_tenant(client)[0]
    _subscribe_and_pay(client, admin)
    receipt_id = client.get("/api/v1/billing/receipts", headers=admin).json()[0]["id"]
    plat = _platform_admin_header(client)
    client.post(
        "/api/v1/platform/tenants",
        headers=plat,
        json={
            "name": "Tenant Kw",
            "slug": "tenant-kw",
            "admin_email": "admin-kw@example.com",
            "admin_password": "rahasia12345",
            "admin_full_name": "Admin Kw",
        },
    )
    other = _login_header(client, "admin-kw@example.com", "rahasia12345")
    assert (
        client.get(f"/api/v1/billing/receipts/{receipt_id}/pdf", headers=other).status_code == 404
    )
    assert client.get("/api/v1/billing/receipts", headers=other).json() == []


def test_penjual_belum_dikonfigurasi_di_produksi(client, billing_env, monkeypatch):  # noqa: F811
    """K8: produksi tanpa identitas penjual -> kwitansi bernomor, unduhan 409."""
    admin, tenant_id = setup_tenant(client)
    monkeypatch.setattr(billing_env, "aeos_seller_name", None)
    monkeypatch.setattr(billing_env, "app_env", "production")
    _issue(client, tenant_id, datetime.now(UTC))
    monkeypatch.setattr(billing_env, "app_env", "test")
    receipt_id = client.get("/api/v1/billing/receipts", headers=admin).json()[0]["id"]
    monkeypatch.setattr(billing_env, "app_env", "production")
    resp = client.get(f"/api/v1/billing/receipts/{receipt_id}/pdf", headers=admin)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Langganan tahunan (#37-40)
# ---------------------------------------------------------------------------


def test_tahunan_tidak_tayang_tanpa_diskon(client, billing_env):  # noqa: F811
    """#37"""
    admin = setup_tenant(client)[0]
    plans = client.get("/api/v1/billing/plans", headers=admin).json()
    assert all(p["annual"]["available"] is False for p in plans)
    resp = client.post(
        "/api/v1/billing/subscribe",
        headers=admin,
        json={"tier": "tier1", "billing_period": "annual"},
    )
    assert resp.status_code == 422


def test_tahunan_dengan_diskon_dan_snapshot(client, billing_env, monkeypatch):  # noqa: F811
    """#38 + #39 harga = 12 x bulanan x (1 - d); snapshot di intent; siklus
    jatah tetap bulanan; ganti env setelah bayar tidak mengubah period_fee.
    Angka diskon 15 HANYA contoh test, bukan keputusan produk."""
    from app.modules.billing.models import TenantBudgetCycle
    from app.modules.billing.service import current_subscription

    monkeypatch.setattr(billing_env, "billing_annual_discount_percent", Decimal("15"))
    admin, tenant_id = setup_tenant(client)
    plans = {p["tier"]: p for p in client.get("/api/v1/billing/plans", headers=admin).json()}
    assert plans["tier1"]["annual"]["fee"] == 5_100_000
    resp = client.post(
        "/api/v1/billing/subscribe",
        headers=admin,
        json={"tier": "tier1", "billing_period": "annual"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["amount"] == 5_100_000 and resp.json()["discount_percent"] == 15
    invoice_id = resp.json()["checkout_url"].split("/")[3]
    webhook(client, {"id": invoice_id, "status": "PAID"})
    monkeypatch.setattr(billing_env, "billing_annual_discount_percent", Decimal("30"))

    def _check(db):
        sub = current_subscription(db, UUID(tenant_id))
        cycle = db.execute(
            select(TenantBudgetCycle).where(TenantBudgetCycle.closed_at.is_(None))
        ).scalar_one()
        return sub, cycle

    sub, cycle = run_in_tenant(client, tenant_id, _check)
    assert sub.billing_period.value == "annual"
    assert sub.period_fee == Decimal("5100000")
    assert sub.discount_percent == Decimal("15")
    assert (sub.current_period_end - sub.started_at.date()).days >= 365
    assert float(cycle.included_budget) == 500_000
    assert (cycle.period_end - cycle.period_start).days == 30
    receipt = client.get("/api/v1/billing/receipts", headers=admin).json()[0]
    assert "Tahunan" in receipt["description"] and "diskon 15%" in receipt["description"]


def test_validasi_env_diskon():
    """#40"""
    from app.core.config import Settings
    from pydantic import ValidationError

    for bad in ("-1", "100"):
        with pytest.raises(ValidationError):
            Settings(billing_annual_discount_percent=bad)
    assert Settings(billing_annual_discount_percent="0").billing_annual_discount_percent == 0
    assert Settings(billing_annual_discount_percent="").billing_annual_discount_percent is None


def test_status_endpoint_belum_berlangganan(client, billing_env):  # noqa: F811
    from tests.conftest import _auth_header

    admin = _auth_header(client)
    _set_commercial(client, _default_tenant_id(client))
    body = client.get("/api/v1/billing/status", headers=admin).json()
    assert body["subscription"] is None
    assert body["access"] == "none" and body["block_reason"] == "no_subscription"
    assert json.dumps(body)  # serializable
