"""Metode bayar tersimpan milik tenant (Fase 28 lanjutan, rencana §3.1/§10).

ATURAN KERAS: modul ini tidak pernah menerima, menyimpan, atau me-log
PAN/nomor kartu/CVV. Kartu ditokenisasi di browser (Xendit.js) -- backend
hanya menerima `card_token_id` dan meneruskannya ke gateway; yang disimpan
hanya ID payment method + metadata tampilan aman yang dikembalikan gateway.

Transaksi DB selalu ditutup (commit) sebelum memanggil gateway.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.payment.base import PaymentMethodDisplay, PaymentMethodResult
from app.modules.billing.models import (
    ChargeStatus,
    PaymentCharge,
    PaymentMethodStatus,
    PaymentMethodType,
    TenantBillingProfile,
    TenantPaymentMethod,
)
from app.modules.billing.service import (
    _get_or_create_credit_account,
    audit_add,
    notify_billing_users,
)

_NPWP_RE = re.compile(r"^[0-9.\-]{15,22}$")


def validate_npwp(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    cleaned = value.strip()
    digits = re.sub(r"\D", "", cleaned)
    if not _NPWP_RE.match(cleaned) or len(digits) not in (15, 16):
        raise HTTPException(status_code=422, detail="NPWP harus 15 atau 16 digit")
    return cleaned


# ---------------------------------------------------------------------------
# Profil penagihan (identitas pembeli)
# ---------------------------------------------------------------------------


def get_or_create_profile(db: Session, tenant_id: UUID) -> TenantBillingProfile:
    from app.modules.platform.models import Tenant

    profile = db.execute(
        select(TenantBillingProfile).where(TenantBillingProfile.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if profile is None:
        tenant = db.get(Tenant, tenant_id)
        profile = TenantBillingProfile(
            tenant_id=tenant_id, legal_name=tenant.name if tenant else "Tenant"
        )
        db.add(profile)
        db.flush()
    return profile


def profile_out(profile: TenantBillingProfile) -> dict:
    return {
        "legal_name": profile.legal_name,
        "npwp": profile.npwp,
        "address": profile.address,
        "billing_email": profile.billing_email,
        "updated_at": profile.updated_at,
    }


def update_profile(
    db: Session,
    tenant_id: UUID,
    *,
    legal_name: str,
    npwp: str | None,
    address: str | None,
    billing_email: str | None,
) -> dict:
    profile = get_or_create_profile(db, tenant_id)
    profile.legal_name = legal_name.strip()
    profile.npwp = validate_npwp(npwp)
    profile.address = address
    profile.billing_email = billing_email
    audit_add(
        db,
        action="billing.billing_profile_updated",
        entity_type="tenant_billing_profile",
        entity_id=profile.id,
        detail={"legal_name": profile.legal_name, "has_npwp": bool(profile.npwp)},
        tenant_id=tenant_id,
    )
    db.commit()
    db.refresh(profile)
    return profile_out(profile)


def ensure_customer_id(db: Session, tenant_id: UUID, fallback_email: str | None) -> str:
    """ID customer gateway milik tenant (dibuat lazy, sekali)."""
    from app.modules.billing.payment_service import get_adapter

    profile = get_or_create_profile(db, tenant_id)
    if profile.provider_customer_id:
        return profile.provider_customer_id
    name = profile.legal_name
    email = profile.billing_email or fallback_email
    profile_id = profile.id
    db.commit()  # tutup transaksi sebelum HTTP
    result = get_adapter().ensure_customer(
        reference_id=f"aeos-cust-{tenant_id}", email=email, name=name
    )
    fresh = db.get(TenantBillingProfile, profile_id)
    assert fresh is not None
    fresh.provider_customer_id = result.provider_customer_id
    db.commit()
    return result.provider_customer_id


# ---------------------------------------------------------------------------
# Metode bayar
# ---------------------------------------------------------------------------


def payment_method_out(pm: TenantPaymentMethod, default_id: UUID | None) -> dict:
    return {
        "id": str(pm.id),
        "type": pm.type.value,
        "status": pm.status.value,
        "card_brand": pm.card_brand,
        "card_last4": pm.card_last4,
        "card_exp_month": pm.card_exp_month,
        "card_exp_year": pm.card_exp_year,
        "ewallet_account_masked": pm.ewallet_account_masked,
        "failure_reason": pm.failure_reason,
        "is_default": pm.id == default_id,
        "label": payment_method_label(pm),
        "created_at": pm.created_at,
        "activated_at": pm.activated_at,
    }


def payment_method_label(pm: TenantPaymentMethod) -> str:
    if pm.type == PaymentMethodType.gopay:
        return f"GoPay {pm.ewallet_account_masked}" if pm.ewallet_account_masked else "GoPay"
    brand = pm.card_brand or "Kartu"
    return f"Kartu {brand} •••• {pm.card_last4}" if pm.card_last4 else f"Kartu {brand}"


def list_payment_methods(db: Session, tenant_id: UUID) -> list[dict]:
    account = _get_or_create_credit_account(db, tenant_id)
    rows = db.execute(
        select(TenantPaymentMethod)
        .where(TenantPaymentMethod.tenant_id == tenant_id)
        .where(TenantPaymentMethod.status != PaymentMethodStatus.removed)
        .order_by(TenantPaymentMethod.created_at.desc())
    ).scalars()
    return [payment_method_out(pm, account.default_payment_method_id) for pm in rows]


def _apply_display(pm: TenantPaymentMethod, display: PaymentMethodDisplay) -> None:
    pm.card_brand = display.card_brand or pm.card_brand
    pm.card_last4 = display.card_last4 or pm.card_last4
    pm.card_exp_month = display.card_exp_month or pm.card_exp_month
    pm.card_exp_year = display.card_exp_year or pm.card_exp_year
    pm.ewallet_account_masked = display.ewallet_account_masked or pm.ewallet_account_masked


def _set_default_if_none(db: Session, pm: TenantPaymentMethod) -> None:
    account = _get_or_create_credit_account(db, pm.tenant_id)
    current = (
        db.get(TenantPaymentMethod, account.default_payment_method_id)
        if account.default_payment_method_id
        else None
    )
    if current is None or current.status != PaymentMethodStatus.active:
        account.default_payment_method_id = pm.id


def add_payment_method(
    db: Session,
    tenant_id: UUID,
    *,
    user_id: UUID | None,
    user_email: str | None,
    type: PaymentMethodType,
    card_token_id: str | None,
) -> dict:
    """Daftarkan metode bayar baru. Kartu: token dari Xendit.js. GoPay:
    memulai account linking -- respons berisi `action.url` untuk redirect.
    Metode aktif pertama otomatis jadi default."""
    from app.modules.billing.payment_service import get_adapter

    if type == PaymentMethodType.card and not card_token_id:
        raise HTTPException(status_code=422, detail="card_token_id wajib untuk kartu")
    adapter = get_adapter()
    customer_id = ensure_customer_id(db, tenant_id, user_email)
    pm_id = uuid4()
    reference_id = f"aeos-pm-{tenant_id}-{pm_id.hex[:12]}"
    base = get_settings().frontend_base_url.rstrip("/")
    db.commit()  # tidak ada transaksi terbuka selama HTTP
    result: PaymentMethodResult = adapter.create_payment_method(
        customer_id=customer_id,
        type=type.value,
        reference_id=reference_id,
        card_token_id=card_token_id,
        success_return_url=f"{base}/billing?pm={pm_id}&result=success",
        failure_return_url=f"{base}/billing?pm={pm_id}&result=failed",
    )
    status = PaymentMethodStatus(result.status)
    pm = TenantPaymentMethod(
        id=pm_id,
        tenant_id=tenant_id,
        provider=adapter.provider_name,
        provider_payment_method_id=result.provider_payment_method_id,
        reference_id=reference_id,
        type=type,
        status=status,
        failure_reason=result.failure_reason,
        created_by=user_id,
        activated_at=datetime.now(UTC) if status == PaymentMethodStatus.active else None,
    )
    _apply_display(pm, result.display)
    db.add(pm)
    db.flush()
    if status == PaymentMethodStatus.active:
        _set_default_if_none(db, pm)
    audit_add(
        db,
        action="billing.payment_method_added",
        entity_type="tenant_payment_method",
        entity_id=pm.id,
        detail={"type": type.value, "status": status.value},
        tenant_id=tenant_id,
    )
    db.commit()
    db.refresh(pm)
    account = _get_or_create_credit_account(db, tenant_id)
    out = payment_method_out(pm, account.default_payment_method_id)
    action = result.actions[0] if result.actions else None
    out["action"] = {"kind": action.kind, "url": action.url} if action else None
    return out


def _get_pm(db: Session, tenant_id: UUID, pm_id: UUID) -> TenantPaymentMethod:
    pm = db.get(TenantPaymentMethod, pm_id)
    if pm is None or pm.tenant_id != tenant_id or pm.status == PaymentMethodStatus.removed:
        raise HTTPException(status_code=404, detail="Metode bayar tidak ditemukan")
    return pm


def set_default(db: Session, tenant_id: UUID, pm_id: UUID) -> list[dict]:
    pm = _get_pm(db, tenant_id, pm_id)
    if pm.status != PaymentMethodStatus.active:
        raise HTTPException(
            status_code=422, detail="Hanya metode bayar aktif yang bisa jadi default"
        )
    account = _get_or_create_credit_account(db, tenant_id)
    previous = account.default_payment_method_id
    account.default_payment_method_id = pm.id
    # Metode bayar baru = kesempatan baru: reset hitungan gagal auto-reload.
    account.auto_reload_failure_count = 0
    account.auto_reload_next_attempt_at = None
    audit_add(
        db,
        action="billing.payment_method_default_changed",
        entity_type="tenant_payment_method",
        entity_id=pm.id,
        detail={"previous": str(previous) if previous else None, "new": str(pm.id)},
        tenant_id=tenant_id,
    )
    db.commit()
    return list_payment_methods(db, tenant_id)


def remove_payment_method(db: Session, tenant_id: UUID, pm_id: UUID, *, force: bool) -> None:
    """Hapus metode bayar: expire di gateway lalu status `removed` (baris
    dipertahankan untuk jejak charge lama). 409 bila charge sedang berjalan
    memakainya, atau bila metode default dipakai auto-reload aktif tanpa
    metode lain (kecuali `force=True`, yang mematikan auto-reload)."""
    from app.modules.billing.payment_service import get_adapter

    pm = _get_pm(db, tenant_id, pm_id)
    in_flight = db.execute(
        select(PaymentCharge.id).where(
            PaymentCharge.payment_method_id == pm.id,
            PaymentCharge.status.in_(
                [ChargeStatus.pending, ChargeStatus.processing, ChargeStatus.unknown]
            ),
        )
    ).first()
    if in_flight is not None:
        raise HTTPException(
            status_code=409, detail="Metode bayar sedang dipakai untuk charge yang berjalan"
        )
    account = _get_or_create_credit_account(db, tenant_id)
    is_default = account.default_payment_method_id == pm.id
    other_active = (
        db.execute(
            select(TenantPaymentMethod)
            .where(TenantPaymentMethod.tenant_id == tenant_id)
            .where(TenantPaymentMethod.status == PaymentMethodStatus.active)
            .where(TenantPaymentMethod.id != pm.id)
            .order_by(TenantPaymentMethod.created_at.desc())
        )
        .scalars()
        .first()
    )
    if is_default and account.auto_reload_enabled and other_active is None and not force:
        raise HTTPException(
            status_code=409,
            detail="Metode bayar ini dipakai auto-reload. Tambah metode lain atau hapus paksa "
            "(auto-reload akan dimatikan).",
        )
    provider_id = pm.provider_payment_method_id
    should_expire = pm.status in (
        PaymentMethodStatus.active,
        PaymentMethodStatus.pending_activation,
    )
    db.commit()
    if should_expire:
        get_adapter().expire_payment_method(provider_id)

    pm = _get_pm(db, tenant_id, pm_id)
    account = _get_or_create_credit_account(db, tenant_id)
    pm.status = PaymentMethodStatus.removed
    pm.removed_at = datetime.now(UTC)
    if account.default_payment_method_id == pm.id:
        account.default_payment_method_id = other_active.id if other_active else None
        if other_active is None and account.auto_reload_enabled:
            account.auto_reload_enabled = False
            audit_add(
                db,
                action="billing.auto_reload_settings_changed",
                entity_type="tenant_credit_account",
                entity_id=account.id,
                detail={"after": {"enabled": False}, "reason": "payment_method_removed"},
                tenant_id=tenant_id,
            )
    audit_add(
        db,
        action="billing.payment_method_removed",
        entity_type="tenant_payment_method",
        entity_id=pm.id,
        detail={"type": pm.type.value, "forced": force},
        tenant_id=tenant_id,
    )
    db.commit()


def find_by_reference(db: Session, reference_id: str) -> TenantPaymentMethod | None:
    return db.execute(
        select(TenantPaymentMethod).where(TenantPaymentMethod.reference_id == reference_id)
    ).scalar_one_or_none()


def apply_payment_method_event(
    db: Session,
    pm: TenantPaymentMethod,
    *,
    status: str,
    display: PaymentMethodDisplay,
    failure_reason: str | None,
) -> bool:
    """Terapkan hasil aktivasi (webhook). Transisi monoton:
    pending_activation -> active/failed; active -> expired. `removed` tidak
    pernah dihidupkan lagi. Return True bila ada perubahan. Tanpa commit."""
    new_status = (
        PaymentMethodStatus(status) if status in PaymentMethodStatus._value2member_map_ else None
    )
    if new_status is None or pm.status == PaymentMethodStatus.removed:
        return False
    allowed = {
        PaymentMethodStatus.pending_activation: {
            PaymentMethodStatus.active,
            PaymentMethodStatus.failed,
            PaymentMethodStatus.expired,
        },
        PaymentMethodStatus.active: {PaymentMethodStatus.expired},
    }
    if new_status not in allowed.get(pm.status, set()):
        return False
    pm.status = new_status
    _apply_display(pm, display)
    if new_status == PaymentMethodStatus.active:
        pm.activated_at = datetime.now(UTC)
        _set_default_if_none(db, pm)
    if new_status == PaymentMethodStatus.failed:
        pm.failure_reason = failure_reason
    if new_status == PaymentMethodStatus.expired:
        account = _get_or_create_credit_account(db, pm.tenant_id)
        if account.default_payment_method_id == pm.id:
            notify_billing_users(
                db,
                pm.tenant_id,
                title="Metode bayar default kedaluwarsa",
                body=f"{payment_method_label(pm)} kedaluwarsa. Perbarui metode bayar agar "
                "auto-reload dan perpanjangan langganan tetap berjalan.",
            )
    suffix = "activated" if new_status == PaymentMethodStatus.active else new_status.value
    audit_add(
        db,
        action=f"billing.payment_method_{suffix}",
        entity_type="tenant_payment_method",
        entity_id=pm.id,
        detail={"status": new_status.value, "failure_reason": failure_reason},
        tenant_id=pm.tenant_id,
    )
    return True
