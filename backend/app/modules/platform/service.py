"""Provisioning tenant oleh platform admin.

Endpoint di bawah /platform hanya bisa diakses role platform_admin
(tenant_id NULL). Operasi di sini berjalan TANPA konteks tenant sehingga
bebas dari filter otomatis — data tenant ditulis secara eksplisit.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import UserRole
from app.modules.auth.schemas import UserCreate
from app.modules.auth.service import create_user, get_by_email
from app.modules.platform.models import (
    LicenseStatus,
    Tenant,
    TenantAppLicense,
    TenantStatus,
)
from app.modules.platform.schemas import (
    TenantCreate,
    TenantOut,
    TenantProvisionedOut,
    TenantUpdate,
)


def _get_tenant(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    return tenant


def get_or_create_default_tenant(
    db: Session, *, name: str = "Default", slug: str = "default"
) -> Tenant:
    """Dipakai bootstrap & test: tenant tunggal untuk mode single-tenant lama."""
    from app.modules.accounting.service import ensure_coa

    existing = db.scalars(select(Tenant).where(Tenant.slug == slug)).first()
    if existing:
        ensure_coa(db, existing.id)
        return existing
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    # Tenant default selalu paket penuh (mode dev/single-tenant).
    ensure_full_package(db, tenant.id)
    ensure_coa(db, tenant.id)
    return tenant


def list_tenants(db: Session) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.created_at)).all())


def provision_tenant(db: Session, payload: TenantCreate) -> TenantProvisionedOut:
    """Buat tenant baru + akun admin pertamanya."""
    slug_taken = db.scalars(select(Tenant).where(Tenant.slug == payload.slug)).first()
    if slug_taken:
        raise HTTPException(status_code=409, detail="Slug sudah dipakai")
    if get_by_email(db, payload.admin_email) is not None:
        raise HTTPException(status_code=409, detail="Email admin sudah terdaftar")

    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    db.flush()  # dapatkan id sebelum membuat user
    # Tenant provisioning baru MULAI TANPA lisensi aplikasi (PRD Fase 7):
    # admin tenant mengaktifkan trial mandiri dari menu Aplikasi, lalu
    # platform admin yang mengatur langganan.
    from app.modules.accounting.service import ensure_coa

    ensure_coa(db, tenant.id)

    admin = create_user(
        db,
        UserCreate(
            email=payload.admin_email,
            full_name=payload.admin_full_name,
            password=payload.admin_password,
            role=UserRole.admin,
        ),
        tenant_id=tenant.id,
    )
    return TenantProvisionedOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        created_at=tenant.created_at,
        admin_email=admin.email,
        admin_initial_password=payload.admin_password,
    )


def update_tenant(db: Session, tenant_id: UUID, payload: TenantUpdate) -> TenantOut:
    tenant = _get_tenant(db, tenant_id)
    if payload.name is not None:
        tenant.name = payload.name
    if payload.status is not None:
        tenant.status = payload.status
    db.commit()
    db.refresh(tenant)
    return TenantOut.model_validate(tenant)


def ensure_active(db: Session, tenant_id: UUID | None) -> None:
    """Blokir request jika tenant ditangguhkan (dipakai saat login)."""
    if tenant_id is None:
        return
    tenant = _get_tenant(db, tenant_id)
    if tenant.status != TenantStatus.active:
        raise HTTPException(status_code=403, detail="Tenant sedang ditangguhkan")


# ---------- Lisensi aplikasi per tenant (Fase 7) ----------


def ensure_full_package(db: Session, tenant_id: UUID) -> None:
    """Aktifkan semua aplikasi registry untuk tenant (paket penuh).

    Dipakai bootstrap/provisioning agar perilaku lama (semua fitur terbuka)
    tetap berjalan; penjualan granular dilakukan dengan mencabut lisensi.
    """
    from app.core.apps import APP_REGISTRY

    existing = set(
        db.scalars(
            select(TenantAppLicense.app_key).where(TenantAppLicense.tenant_id == tenant_id)
        ).all()
    )
    for key in APP_REGISTRY:
        if key in existing:
            continue
        db.add(
            TenantAppLicense(
                tenant_id=tenant_id,
                app_key=key,
                status=LicenseStatus.active,
                expires_at=None,
            )
        )
    db.commit()


def is_licensed(db: Session, tenant_id: UUID | None, app_key: str) -> bool:
    """True bila lisensi aktif atau trial yang belum kedaluwarsa."""
    from datetime import UTC, datetime

    if tenant_id is None:
        return False
    license_row = db.execute(
        select(TenantAppLicense)
        .where(TenantAppLicense.tenant_id == tenant_id)
        .where(TenantAppLicense.app_key == app_key)
    ).scalar_one_or_none()
    if license_row is None:
        return False
    if license_row.status == LicenseStatus.active:
        return True
    if license_row.status == LicenseStatus.trial:
        expires = license_row.expires_at
        if expires is None:
            return False
        now = datetime.now(UTC)
        if expires.tzinfo is None:  # SQLite menyimpan naive
            now = now.replace(tzinfo=None)
        return expires > now
    return False


def activate_trial(db: Session, tenant_id: UUID, app_key: str) -> TenantAppLicense:
    """Aktivasi trial 14 hari mandiri; satu kali per aplikasi per tenant."""
    import uuid as _uuid
    from datetime import UTC, datetime, timedelta

    from app.core.apps import APP_REGISTRY, TRIAL_DAYS

    if app_key not in APP_REGISTRY:
        raise HTTPException(status_code=404, detail="Aplikasi tidak dikenal")
    existing = db.execute(
        select(TenantAppLicense)
        .where(TenantAppLicense.tenant_id == tenant_id)
        .where(TenantAppLicense.app_key == app_key)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Trial hanya sekali per aplikasi; hubungi platform untuk berlangganan",
        )
    license_row = TenantAppLicense(
        id=_uuid.uuid4(),
        tenant_id=tenant_id,
        app_key=app_key,
        status=LicenseStatus.trial,
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=TRIAL_DAYS),
    )
    # Baris dibuat dari konteks tenant → tenant_id diinjeksi otomatis;
    # set eksplisit di atas menjaga kejelasan saat dipanggil tanpa konteks.
    db.add(license_row)
    db.commit()
    db.refresh(license_row)
    return license_row


def list_tenant_licenses(db: Session, tenant_id: UUID) -> list[TenantAppLicense]:
    return list(
        db.execute(
            select(TenantAppLicense)
            .where(TenantAppLicense.tenant_id == tenant_id)
            .order_by(TenantAppLicense.app_key)
        ).scalars()
    )


def set_license_status(
    db: Session,
    tenant_id: UUID,
    app_key: str,
    status: LicenseStatus,
    expires_at=None,
) -> TenantAppLicense:
    """Platform admin mengatur lisensi: aktifkan/perpanjang/cabut/trial."""
    from app.core.apps import APP_REGISTRY

    if app_key not in APP_REGISTRY:
        raise HTTPException(status_code=404, detail="Aplikasi tidak dikenal")
    license_row = db.execute(
        select(TenantAppLicense)
        .where(TenantAppLicense.tenant_id == tenant_id)
        .where(TenantAppLicense.app_key == app_key)
    ).scalar_one_or_none()
    if license_row is None:
        license_row = TenantAppLicense(tenant_id=tenant_id, app_key=app_key)
        db.add(license_row)
    license_row.status = status
    license_row.expires_at = expires_at
    db.commit()
    db.refresh(license_row)
    return license_row
