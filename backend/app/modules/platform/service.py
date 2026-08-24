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
from app.modules.platform.models import Tenant, TenantStatus
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
    existing = db.scalars(select(Tenant).where(Tenant.slug == slug)).first()
    if existing:
        return existing
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
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
