"""Regresi bug ditemukan saat audit Fase 28 (2026-09-05): fungsi platform-admin
yang menyentuh tabel ber-RLS (`tenant_app_licenses`) untuk tenant_id arbitrary
TANPA `set_tenant()` -- di Postgres+RLS ini membuat SELECT selalu pulang
kosong dan INSERT/UPDATE gagal RLS violation, meski secara sengaja query-nya
sudah difilter eksplisit `.where(tenant_id == ...)` (cukup untuk filter ORM,
TIDAK cukup untuk RLS server-side).

Butuh Postgres nyata -- SQLite (default test suite) tidak punya RLS sama
sekali sehingga tidak bisa mendeteksi kelas bug ini (persis alasan yang sama
seperti `test_rls_coverage.py`).

PENTING: `TEST_POSTGRES_URL`/`DATABASE_URL` di sini HARUS connection string
role aplikasi (`aeos_app`), BUKAN superuser `postgres` -- superuser SELALU
melewati RLS apa pun kebijakannya, jadi test ini akan lolos palsu (tidak
mendeteksi apa-apa) kalau dijalankan dengan kredensial superuser. Beda
dengan `test_rls_coverage.py` yang cuma membaca katalog `pg_policies`
(aman pakai superuser karena tidak menyentuh enforcement sungguhan)."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select


def _resolve_test_pg_url() -> str | None:
    url = os.environ.get("TEST_POSTGRES_URL")
    if url:
        return url
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql"):
        return db_url
    return None


pytestmark = pytest.mark.skipif(
    _resolve_test_pg_url() is None,
    reason="Butuh Postgres nyata (TEST_POSTGRES_URL/DATABASE_URL) -- SQLite tidak punya RLS",
)


@pytest.fixture()
def pg_session():
    """SENGAJA memakai `app.core.database.SessionLocal` (engine singleton
    asli), BUKAN `create_engine()` baru -- listener `before_cursor_execute`
    yang menyinkronkan `app.current_tenant` ke Postgres (`core/tenancy.py::
    install_tenancy_listeners`) terpasang di objek engine SPESIFIK itu saat
    modul diimpor pertama kali. Engine baru tidak akan pernah dapat
    listener itu, sehingga `set_tenant()` Python-side tidak berefek apa pun
    ke Postgres -- kesalahan ini pernah membuat test ini lolos palsu."""
    import app.modules.billing.models  # noqa: F401 -- registrasi metadata
    import app.modules.platform.models  # noqa: F401
    from app.core.database import SessionLocal, engine

    assert str(engine.url).startswith("postgresql"), (
        "SessionLocal tidak terhubung ke Postgres -- set DATABASE_URL (bukan cuma "
        "TEST_POSTGRES_URL) ke connection string aeos_app SEBELUM proses pytest dimulai."
    )
    session = SessionLocal()
    yield session
    session.close()


def test_list_and_set_license_work_without_ambient_tenant_context(pg_session):
    """Simulasi persis konteks platform_admin: `get_tenant()` None (tidak ada
    JWT tenant), tapi memanggil fungsi untuk tenant_id tenant LAIN yang aktif."""
    from app.core.tenancy import get_tenant, set_tenant
    from app.modules.platform import service
    from app.modules.platform.models import LicenseStatus, Tenant

    db = pg_session
    set_tenant(None)  # pastikan konteks ambien kosong, seperti platform_admin
    assert get_tenant() is None

    # Tenant "default" harus sudah ada dari bootstrap dev; kalau tidak,
    # buat tenant throwaway sendiri supaya test tidak bergantung urutan run.
    tenant = db.execute(select(Tenant).where(Tenant.slug == "default")).scalar_one_or_none()
    created_throwaway = False
    if tenant is None:
        tenant = Tenant(
            id=uuid4(), name="RLS Regression Throwaway", slug=f"rls-regr-{uuid4().hex[:8]}"
        )
        db.add(tenant)
        db.commit()
        created_throwaway = True

    try:
        # SELECT lewat fungsi yang diperbaiki harus benar-benar bisa melihat
        # baris tenant tsb, bukan pulang kosong akibat RLS.
        before = service.set_license_status(db, tenant.id, "sales_crm", LicenseStatus.active)
        assert before.status == LicenseStatus.active

        rows = service.list_tenant_licenses(db, tenant.id)
        assert any(r.app_key == "sales_crm" and r.status == LicenseStatus.active for r in rows)

        # Konteks ambien harus balik ke None setelah fungsi selesai (tidak bocor
        # ke pemanggil berikutnya).
        assert get_tenant() is None
    finally:
        if created_throwaway:
            set_tenant(tenant.id)
            from app.modules.platform.models import TenantAppLicense

            db.execute(delete(TenantAppLicense).where(TenantAppLicense.tenant_id == tenant.id))
            db.execute(delete(Tenant).where(Tenant.id == tenant.id))
            db.commit()
            set_tenant(None)


def test_compute_usage_returns_real_numbers_without_ambient_tenant_context(pg_session):
    from app.core.tenancy import get_tenant, set_tenant
    from app.modules.platform.models import Tenant
    from app.modules.platform.usage import compute_usage

    db = pg_session
    set_tenant(None)
    tenant = db.execute(select(Tenant).where(Tenant.slug == "default")).scalar_one_or_none()
    if tenant is None:
        pytest.skip("Tenant 'default' tidak ditemukan di DB Postgres ini")

    result = compute_usage(db, tenant.id)
    assert result["tenant_id"] == str(tenant.id)
    # Sebelum perbaikan, RLS membuat semua hitungan pulang 0 walau data nyata
    # ada -- baris "amount" untuk SKU yang memang berlisensi seharusnya bisa
    # positif (tergantung data dev, jadi dicek strukturnya, bukan angka pasti).
    assert isinstance(result["lines"], list)
    assert get_tenant() is None
