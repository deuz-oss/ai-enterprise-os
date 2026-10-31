from datetime import date
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


@router.post("/internal/run-auto-reload")
def run_auto_reload(db: Session = Depends(get_db)):
    """Eksekusi & rekonsiliasi charge auto-reload semua tenant + pemicu
    proaktif (saldo di bawah ambang). Dipicu cron eksternal tiap ~2 menit
    (K11). Aman dipanggil berulang/paralel (compare-and-set per charge)."""
    from app.modules.billing.auto_reload import run_auto_reload_for_all_tenants

    return run_auto_reload_for_all_tenants(db)


@router.post("/internal/run-renewals")
def run_renewals(db: Session = Depends(get_db)):
    """Perpanjangan langganan harian (mis. 01:00 WIB): invoice H-7, charge
    metode bayar tersimpan, retry menunggak, pembatalan otomatis."""
    from app.modules.billing.renewal import run_renewals_for_all_tenants

    return run_renewals_for_all_tenants(db)


@router.post("/tenants/{tenant_id}/billing/unblock-metered")
def unblock_metered(tenant_id: UUID, db: Session = Depends(get_db)):
    """Cabut penanda blokir metered + reset hitungan gagal auto-reload
    (intervensi support). Blokir efektif tetap mengikuti sisa saldo."""
    from app.modules.billing.service import _get_or_create_credit_account, audit_add

    service._get_tenant(db, tenant_id)
    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        account = _get_or_create_credit_account(db, tenant_id)
        account.metered_blocked_at = None
        account.metered_block_reason = None
        account.auto_reload_failure_count = 0
        account.auto_reload_next_attempt_at = None
        audit_add(
            db,
            action="platform.metered_unblocked",
            entity_type="tenant_credit_account",
            entity_id=account.id,
            tenant_id=tenant_id,
        )
        db.commit()
    finally:
        set_tenant(previous_tenant)
    return {"status": "ok"}


@router.get("/billing/webhook-events")
def list_webhook_events(status: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
    """Investigasi event webhook gateway (tabel platform tanpa tenant)."""
    from app.modules.billing.models import PaymentWebhookEvent, WebhookEventStatus

    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit harus 1-200")
    stmt = select(PaymentWebhookEvent).order_by(PaymentWebhookEvent.received_at.desc())
    if status is not None:
        try:
            stmt = stmt.where(PaymentWebhookEvent.status == WebhookEventStatus(status))
        except ValueError:
            raise HTTPException(status_code=422, detail="status tidak valid") from None
    rows = db.execute(stmt.limit(limit)).scalars()
    return [
        {
            "id": str(r.id),
            "provider": r.provider,
            "event_type": r.event_type,
            "object_id": r.object_id,
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            "status": r.status.value,
            "error": r.error,
            "received_at": r.received_at,
            "processed_at": r.processed_at,
        }
        for r in rows
    ]


@router.post("/internal/run-weekly-digest")
def run_weekly_digest(db: Session = Depends(get_db)):
    """Digest kepatuhan kontrak & BPJS (AI #4) untuk semua tenant aktif.
    Dipicu cron OS eksternal (mis. Senin 07:00) -- pola sama dengan
    run-cycle-charge. Idempoten per tenant per minggu ISO; tanpa cron pun
    digest tetap terbuat lewat safety-net saat admin/HR membuka aplikasi."""
    from app.modules.hrd.compliance_digest import run_weekly_digest_for_all_tenants

    sent = run_weekly_digest_for_all_tenants(db)
    return {"tenants_sent": len(sent), "recipients": sent}


@router.get("/tenants/{tenant_id}/billing-summary")
def get_tenant_billing_summary(tenant_id: UUID, db: Session = Depends(get_db)):
    """Ringkasan tier + saldo + 5 transaksi terakhir untuk panel "Billing
    Opsi G" di PlatformTenants.tsx (Milestone 8). Konteks tenant di-set
    manual sebelum query tabel ber-RLS -- endpoint ini berjalan di bawah
    platform_admin, tanpa konteks tenant aktif secara default (lihat
    catatan RLS di `billing/cycle_close.py`)."""
    from app.modules.billing.models import ChargeStatus, PaymentCharge
    from app.modules.billing.payment_methods import payment_method_label
    from app.modules.billing.service import (
        _get_or_create_credit_account,
        current_subscription,
        default_payment_method,
        get_balance_summary,
        list_transactions,
    )

    service._get_tenant(db, tenant_id)
    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        subscription = current_subscription(db, tenant_id)
        summary = get_balance_summary(db, tenant_id)
        recent = list_transactions(db, tenant_id, limit=5, offset=0)
        account = _get_or_create_credit_account(db, tenant_id)
        pm = default_payment_method(db, account)
        last_failure = (
            db.execute(
                select(PaymentCharge)
                .where(PaymentCharge.tenant_id == tenant_id)
                .where(PaymentCharge.status == ChargeStatus.failed)
                .order_by(PaymentCharge.completed_at.desc())
            )
            .scalars()
            .first()
        )
        billing_extra = {
            "billing_period": subscription.billing_period.value if subscription else None,
            "current_period_end": subscription.current_period_end if subscription else None,
            "past_due_since": subscription.past_due_since if subscription else None,
            "metered_blocked": summary["state"] == "empty"
            or account.metered_blocked_at is not None,
            "block_reason": account.metered_block_reason,
            "default_payment_method": payment_method_label(pm) if pm else None,
            "auto_reload_enabled": account.auto_reload_enabled,
            "last_payment_failure": {
                "purpose": last_failure.purpose.value,
                "failure_code": last_failure.failure_code,
                "at": last_failure.completed_at,
            }
            if last_failure
            else None,
        }
        db.commit()
    finally:
        set_tenant(previous_tenant)
    return {
        "tier": subscription.tier.value if subscription else None,
        "subscription_status": subscription.status.value if subscription else None,
        **billing_extra,
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
    billing_period: str = "monthly"
    # Kosong = baris legacy (pembayaran di luar sistem) yang TIDAK dikunci
    # penegakan renewal; diisi = masa bayar yang diakui support.
    current_period_end: date | None = None


@router.patch("/tenants/{tenant_id}/subscription")
def override_subscription(
    tenant_id: UUID, payload: SubscriptionOverrideIn, db: Session = Depends(get_db)
):
    """Set tier langganan tenant langsung, bypass Xendit -- dipakai script
    migrasi one-shot (Milestone 9) dan intervensi support/manual platform
    admin (mis. tenant yang bayar di luar sistem)."""
    from app.modules.billing.models import TIER_MONTHLY_FEE_IDR, BillingPeriod, SubscriptionTier
    from app.modules.billing.payment_service import _activate_subscription
    from app.modules.billing.service import audit_add

    try:
        tier = SubscriptionTier(payload.tier)
        period = BillingPeriod(payload.billing_period)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Tier tidak valid; gunakan {', '.join(t.value for t in SubscriptionTier)}",
        ) from None

    service._get_tenant(db, tenant_id)
    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        # Override = pembayaran di luar sistem: tanpa kwitansi (K15).
        sub = _activate_subscription(
            db,
            tenant_id,
            tier,
            TIER_MONTHLY_FEE_IDR[tier],
            billing_period=period,
            set_period_end=False,
            current_period_end=payload.current_period_end,
        )
        audit_add(
            db,
            action="platform.subscription_overridden",
            entity_type="tenant_subscription",
            entity_id=sub.id,
            detail={
                "tier": tier.value,
                "billing_period": period.value,
                "current_period_end": str(payload.current_period_end)
                if payload.current_period_end
                else None,
            },
            tenant_id=tenant_id,
        )
        db.commit()
    finally:
        set_tenant(previous_tenant)
    return {"status": "ok", "tier": tier.value, "billing_period": period.value}
