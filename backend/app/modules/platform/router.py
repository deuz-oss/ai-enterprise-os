from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.apps import APP_REGISTRY, BUNDLE_REGISTRY
from app.core.database import get_db
from app.core.security import get_current_user, require_platform_admin
from app.core.tenancy import get_tenant, set_tenant
from app.modules.apps.schemas import LicenseSetIn
from app.modules.platform import service, usage
from app.modules.platform.models import LicenseStatus, TenantAppLicense
from app.modules.platform.schemas import (
    BillingModeUpdate,
    TenantCreate,
    TenantOut,
    TenantProvisionedOut,
    TenantUpdate,
)

# Khusus platform_admin: mengelola daftar tenant SaaS.
# Guard khusus tanpa bypass "admin" agar admin tenant tidak ikut lolos.
router = APIRouter(
    prefix="/platform",
    tags=["platform"],
    dependencies=[Depends(get_current_user), Depends(require_platform_admin())],
)


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return service.list_tenants(db)


@router.post("/tenants", response_model=TenantProvisionedOut, status_code=201)
def provision_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    return service.provision_tenant(db, payload)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: UUID, payload: TenantUpdate, db: Session = Depends(get_db)):
    return service.update_tenant(db, tenant_id, payload)


@router.patch("/tenants/{tenant_id}/billing-mode", response_model=TenantOut)
def set_billing_mode(tenant_id: UUID, payload: BillingModeUpdate, db: Session = Depends(get_db)):
    """PRD v3.0 per-tenant override inherit|internal|commercial + audit."""
    tenant = service._get_tenant(db, tenant_id)
    tenant.billing_mode = payload.billing_mode
    db.commit()
    db.refresh(tenant)
    try:
        from app.modules.audit.service import log_event

        log_event(
            db,
            action="tenant.billing_mode_changed",
            entity_type="tenant",
            entity_id=str(tenant.id),
            detail={"billing_mode": payload.billing_mode},
        )
    except Exception:
        pass
    return tenant


@router.get("/tenants/{tenant_id}/usage")
def get_tenant_usage(tenant_id: UUID, period: str | None = None, db: Session = Depends(get_db)):
    """Estimasi pemakaian & tagihan (PRD v3.0 §2) — read-only, tidak menagih.

    `period` format YYYY-MM (default bulan berjalan).
    """
    if period is not None:
        try:
            year_s, month_s = period.split("-")
            if not (1 <= int(month_s) <= 12) or len(year_s) != 4:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=422, detail="Format period harus YYYY-MM") from None
    return usage.compute_usage(db, tenant_id, period)


# ---------- Lisensi aplikasi per tenant ----------


@router.get("/tenants/{tenant_id}/licenses")
def list_licenses(tenant_id: UUID, db: Session = Depends(get_db)):
    service._get_tenant(db, tenant_id)
    rows = {row.app_key: row for row in service.list_tenant_licenses(db, tenant_id)}
    result = []
    for key, spec in APP_REGISTRY.items():
        row: TenantAppLicense | None = rows.get(key)
        result.append(
            {
                "app_key": key,
                "name": spec.name,
                "status": row.status.value if row else None,
                "expires_at": row.expires_at if row else None,
            }
        )
    return result


@router.patch("/tenants/{tenant_id}/licenses/{app_key}")
def set_license(
    tenant_id: UUID,
    app_key: str,
    payload: LicenseSetIn,
    db: Session = Depends(get_db),
):
    """Aktifkan/perpanjang/cabut lisensi aplikasi satu tenant."""
    try:
        status_enum = LicenseStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Status tidak valid; gunakan {', '.join(s.value for s in LicenseStatus)}",
        ) from None
    row = service.set_license_status(db, tenant_id, app_key, status_enum, payload.expires_at)
    return {
        "app_key": row.app_key,
        "status": row.status.value,
        "expires_at": row.expires_at,
    }


# ---------- Bundle komersial Opsi F (4 paket = gabungan SKU teknis) ----------


@router.get("/bundles")
def list_bundles():
    """4 bundel komersial Opsi F + isi SKU teknisnya — dipakai UI Lisensi supaya
    grouping bundle bersumber dari backend, bukan hardcode di frontend."""
    return [
        {
            "key": b.key,
            "name": b.name,
            "apps": list(b.apps),
            "description": b.description,
            "price_model": b.price_model,
        }
        for b in BUNDLE_REGISTRY.values()
        if b.apps  # Foundation/starter/growth/dst di luar 4 bundel F tak relevan di sini
        and b.key in {"talent", "workforce", "revenue", "govern"}
    ]


@router.patch("/tenants/{tenant_id}/bundles/{bundle_key}")
def set_bundle(
    tenant_id: UUID,
    bundle_key: str,
    payload: LicenseSetIn,
    db: Session = Depends(get_db),
):
    """Aktifkan/perpanjang/cabut SEMUA app teknis dalam satu bundle Opsi F
    sekaligus (mis. "talent" -> sales_crm + recruitment bersamaan) — mencegah
    bundle komersial "setengah aktif" akibat app_key diatur satu-satu."""
    try:
        status_enum = LicenseStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Status tidak valid; gunakan {', '.join(s.value for s in LicenseStatus)}",
        ) from None
    rows = service.set_bundle_status(db, tenant_id, bundle_key, status_enum, payload.expires_at)
    return [
        {"app_key": row.app_key, "status": row.status.value, "expires_at": row.expires_at}
        for row in rows
    ]


# ---------- Billing Opsi G (Fase 28) ----------


@router.post("/internal/run-cycle-charge")
def run_cycle_charge(db: Session = Depends(get_db)):
    """Tutup `TenantBudgetCycle` yang sudah lewat waktunya untuk SEMUA
    tenant, mendebit biaya snapshot (talent aktif, employee aktif) dari
    cycle baru. Dipicu scheduler OS eksternal (cron/Task Scheduler) --
    tidak ada scheduler in-process di codebase ini (keputusan Fase 28).
    Idempotent per tenant, aman dipanggil berulang."""
    from app.modules.billing.cycle_close import run_cycle_charge_for_all_tenants

    closed = run_cycle_charge_for_all_tenants(db)
    return {"closed_count": len(closed), "tenant_ids": [str(t) for t in closed]}


@router.get("/tenants/{tenant_id}/billing-summary")
def get_tenant_billing_summary(tenant_id: UUID, db: Session = Depends(get_db)):
    """Ringkasan tier + saldo + 5 transaksi terakhir untuk panel "Billing
    Opsi G" di PlatformTenants.tsx (Milestone 8). Konteks tenant di-set
    manual sebelum query tabel ber-RLS -- endpoint ini berjalan di bawah
    platform_admin, tanpa konteks tenant aktif secara default (lihat
    catatan RLS di `billing/cycle_close.py`)."""
    from app.modules.billing.models import SubscriptionStatus, TenantSubscription
    from app.modules.billing.service import get_balance_summary, list_transactions

    service._get_tenant(db, tenant_id)
    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        subscription = db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .where(TenantSubscription.status == SubscriptionStatus.active)
        ).scalar_one_or_none()
        summary = get_balance_summary(db, tenant_id)
        recent = list_transactions(db, tenant_id, limit=5, offset=0)
    finally:
        set_tenant(previous_tenant)
    return {
        "tier": subscription.tier.value if subscription else None,
        "subscription_status": subscription.status.value if subscription else None,
        **summary,
        "recent_transactions": [
            {
                "id": str(t.id),
                "type": t.type.value,
                "amount": float(t.amount),
                "ref_event": t.ref_event,
                "created_at": t.created_at,
            }
            for t in recent
        ],
    }


class SubscriptionOverrideIn(BaseModel):
    tier: str


@router.patch("/tenants/{tenant_id}/subscription")
def override_subscription(
    tenant_id: UUID, payload: SubscriptionOverrideIn, db: Session = Depends(get_db)
):
    """Set tier langganan tenant langsung, bypass Xendit -- dipakai script
    migrasi one-shot (Milestone 9) dan intervensi support/manual platform
    admin (mis. tenant yang bayar di luar sistem)."""
    from app.modules.billing.models import TIER_MONTHLY_FEE_IDR, SubscriptionTier
    from app.modules.billing.payment_service import _activate_subscription

    try:
        tier = SubscriptionTier(payload.tier)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Tier tidak valid; gunakan {', '.join(t.value for t in SubscriptionTier)}",
        ) from None

    service._get_tenant(db, tenant_id)
    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        _activate_subscription(db, tenant_id, tier, TIER_MONTHLY_FEE_IDR[tier])
        db.commit()
    finally:
        set_tenant(previous_tenant)
    return {"status": "ok", "tier": tier.value}
