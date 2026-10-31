"""Fase 28 lanjutan: metode bayar tersimpan (rencana §13 kasus 1-9).

Sandbox adapter saja -- tanpa kredensial Xendit sungguhan.
"""

from uuid import UUID

from app.core.database import Base

from tests.billing_support import (  # noqa: F401 - fixture
    add_card,
    billing_env,
    enable_auto_reload,
    run_in_tenant,
    setup_tenant,
)
from tests.conftest import _auth_header, _login_header


def test_tambah_kartu_aktif_jadi_default(client, billing_env):  # noqa: F811
    """#1 kartu sbx-tok-ok -> aktif, metadata tampilan, otomatis default."""
    admin, _ = setup_tenant(client)
    pm = add_card(client, admin)
    assert pm["status"] == "active"
    assert pm["card_brand"] == "VISA"
    assert pm["card_last4"] == "4242"
    assert pm["card_exp_month"] == 12 and pm["card_exp_year"] == 2030
    assert pm["is_default"] is True
    assert pm["action"] is None
    listed = client.get("/api/v1/billing/payment-methods", headers=admin).json()
    assert [p["id"] for p in listed] == [pm["id"]]


def test_kartu_3ds_aktif_setelah_webhook(client, billing_env):  # noqa: F811
    """#2 sbx-tok-3ds -> pending + action.url; simulasi aktivasi -> aktif."""
    admin, tenant_id = setup_tenant(client)
    pm = add_card(client, admin, "sbx-tok-3ds")
    assert pm["status"] == "pending_activation"
    assert pm["action"]["url"].startswith("/sandbox/billing/payment-methods/")
    assert pm["is_default"] is False

    def _ref(db):
        from app.modules.billing.models import TenantPaymentMethod

        return db.get(TenantPaymentMethod, UUID(pm["id"])).reference_id

    reference = run_in_tenant(client, tenant_id, _ref)
    resp = client.post(
        f"/api/v1/billing/sandbox/payment-methods/{reference}/activate", headers=admin
    )
    assert resp.status_code == 200, resp.text
    listed = client.get("/api/v1/billing/payment-methods", headers=admin).json()
    assert listed[0]["status"] == "active"
    assert listed[0]["is_default"] is True


def test_gopay_linking_lewat_webhook(client, billing_env):  # noqa: F811
    """#3 GoPay -> pending_activation; webhook payment_method.activated -> aktif
    dengan nomor tersamar dari gateway."""
    admin, tenant_id = setup_tenant(client)
    resp = client.post("/api/v1/billing/payment-methods", headers=admin, json={"type": "gopay"})
    assert resp.status_code == 201, resp.text
    pm = resp.json()
    assert pm["status"] == "pending_activation"
    assert pm["action"] is not None

    def _ref(db):
        from app.modules.billing.models import TenantPaymentMethod

        return db.get(TenantPaymentMethod, UUID(pm["id"])).reference_id

    reference = run_in_tenant(client, tenant_id, _ref)
    client.post(f"/api/v1/billing/sandbox/payment-methods/{reference}/activate", headers=admin)
    listed = client.get("/api/v1/billing/payment-methods", headers=admin).json()
    assert listed[0]["status"] == "active"
    assert listed[0]["ewallet_account_masked"] == "0812****7890"
    assert listed[0]["label"].startswith("GoPay")


def test_data_kartu_mentah_ditolak(client, billing_env):  # noqa: F811
    """#4 field card_number/cvv -> 422 (extra=forbid)."""
    admin, _ = setup_tenant(client)
    resp = client.post(
        "/api/v1/billing/payment-methods",
        headers=admin,
        json={"type": "card", "card_number": "4000000000000002", "cvv": "123"},
    )
    assert resp.status_code == 422


def test_skema_tanpa_kolom_pan_cvv():
    """#5 regresi skema: tidak ada kolom mirip PAN/CVV di tabel mana pun."""
    forbidden = ("pan", "card_number", "cvv", "cvc", "cvn")
    for table in Base.metadata.tables.values():
        for column in table.columns:
            name = column.name.lower()
            assert name not in forbidden, f"{table.name}.{column.name}"
            assert "card_number" not in name and "cvv" not in name, f"{table.name}.{column.name}"


def test_hapus_default_saat_auto_reload_aktif(client, billing_env, monkeypatch):  # noqa: F811
    """#6 hapus PM default + auto-reload aktif tanpa PM lain -> 409; force ->
    auto-reload mati & expire_payment_method terpanggil."""
    from app.core.payment import sandbox

    admin, _ = setup_tenant(client)
    pm = add_card(client, admin)
    enable_auto_reload(client, admin)
    expired: list[str] = []
    monkeypatch.setattr(
        sandbox.SandboxPaymentAdapter,
        "expire_payment_method",
        lambda self, pid: expired.append(pid),
    )
    blocked = client.delete(f"/api/v1/billing/payment-methods/{pm['id']}", headers=admin)
    assert blocked.status_code == 409, blocked.text
    forced = client.delete(f"/api/v1/billing/payment-methods/{pm['id']}?force=true", headers=admin)
    assert forced.status_code == 204, forced.text
    assert len(expired) == 1
    settings_now = client.get("/api/v1/billing/auto-reload-settings", headers=admin).json()
    assert settings_now["enabled"] is False
    assert client.get("/api/v1/billing/payment-methods", headers=admin).json() == []


def test_default_hanya_untuk_pm_aktif(client, billing_env):  # noqa: F811
    """#7 set default ke PM pending -> 422; ke PM terhapus -> 404."""
    admin, _ = setup_tenant(client)
    add_card(client, admin)
    pending = add_card(client, admin, "sbx-tok-3ds")
    resp = client.post(f"/api/v1/billing/payment-methods/{pending['id']}/default", headers=admin)
    assert resp.status_code == 422
    extra = add_card(client, admin)
    client.delete(f"/api/v1/billing/payment-methods/{extra['id']}", headers=admin)
    resp = client.post(f"/api/v1/billing/payment-methods/{extra['id']}/default", headers=admin)
    assert resp.status_code == 404


def test_isolasi_tenant_payment_method(client, billing_env):  # noqa: F811
    """#8 tenant lain tidak bisa melihat/menghapus/set default PM tenant A."""
    from tests.conftest import _platform_admin_header

    admin, _ = setup_tenant(client)
    pm = add_card(client, admin)
    plat = _platform_admin_header(client)
    other = client.post(
        "/api/v1/platform/tenants",
        headers=plat,
        json={
            "name": "Tenant B",
            "slug": "tenant-b-billing",
            "admin_email": "admin-b-billing@example.com",
            "admin_password": "rahasia12345",
            "admin_full_name": "Admin B",
        },
    )
    assert other.status_code == 201, other.text
    admin_b = _login_header(client, "admin-b-billing@example.com", "rahasia12345")
    assert client.get("/api/v1/billing/payment-methods", headers=admin_b).json() == []
    resp = client.post(f"/api/v1/billing/payment-methods/{pm['id']}/default", headers=admin_b)
    assert resp.status_code == 404
    resp = client.delete(f"/api/v1/billing/payment-methods/{pm['id']}", headers=admin_b)
    assert resp.status_code == 404


def test_role_guard_payment_methods(client, billing_env):  # noqa: F811
    """#9 role operations -> 403; finance & admin lolos."""
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate

    from tests.conftest import _seed_user_idempotent

    _auth_header(client)
    setup_tenant(client)
    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        for role in ("operations", "finance"):
            _seed_user_idempotent(
                db,
                UserCreate(
                    email=f"{role}-billing@example.com",
                    password="rahasia12345",
                    full_name=role,
                    role=role,
                ),
                tenant.id,
            )
    finally:
        db.close()

    ops = _login_header(client, "operations-billing@example.com", "rahasia12345")
    fin = _login_header(client, "finance-billing@example.com", "rahasia12345")
    assert client.get("/api/v1/billing/payment-methods", headers=ops).status_code == 403
    assert client.get("/api/v1/billing/payment-methods", headers=fin).status_code == 200
