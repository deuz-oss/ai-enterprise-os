"""Eksekusi charge merchant-initiated (metode bayar tersimpan) untuk
auto-reload & renewal (Fase 28 lanjutan, rencana §6.2-§6.4).

Invarian:
- Klaim charge lewat compare-and-set status (`pending/unknown/processing`
  -> `processing` + tenggat klaim di `next_retry_at`), lalu COMMIT sebelum
  memanggil gateway -- tidak ada transaksi DB terbuka selama HTTP.
- Hasil `unknown` (timeout/5xx) direkonsiliasi dulu lewat
  `get_charge_by_reference` dengan idempotency key yang SAMA; tidak pernah
  membuat key baru untuk percobaan yang sama.
- Sukses/gagal diterapkan lewat compare-and-set status sehingga respons
  sinkron dan webhook yang datang bersamaan hanya menerapkan efek sekali.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.core.payment.base import ChargeResult, PaymentGatewayTimeout
from app.modules.billing.models import (
    ChargePurpose,
    ChargeStatus,
    PaymentCharge,
    TenantBillingProfile,
    TenantPaymentMethod,
)
from app.modules.billing.service import as_aware, audit_add, now_utc

logger = logging.getLogger(__name__)

CLAIM_WINDOW = timedelta(minutes=5)
UNKNOWN_RETRY = timedelta(minutes=2)
PENDING_RECHECK = timedelta(minutes=5)
_RETRYABLE = (ChargeStatus.pending, ChargeStatus.unknown, ChargeStatus.processing)


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def execute_charge(db: Session, charge_id: UUID) -> PaymentCharge:
    """Jalankan (atau rekonsiliasi) satu charge. Aman dipanggil paralel/berulang.
    Pemanggil wajib sudah berada di konteks tenant pemilik charge."""
    from app.modules.billing.payment_service import get_adapter

    charge = db.get(PaymentCharge, charge_id)
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge tidak ditemukan")
    previous = charge.status
    if previous not in _RETRYABLE:
        return charge
    now = now_utc()
    old_deadline = charge.next_retry_at
    aware_deadline = as_aware(old_deadline)
    if previous != ChargeStatus.pending and aware_deadline is not None and aware_deadline > now:
        return charge  # sedang diklaim eksekutor lain / belum waktunya
    deadline_cond = (
        PaymentCharge.next_retry_at.is_(None)
        if old_deadline is None
        else PaymentCharge.next_retry_at == old_deadline
    )
    claimed = db.execute(
        update(PaymentCharge)
        .where(PaymentCharge.id == charge_id, PaymentCharge.status == previous, deadline_cond)
        .values(status=ChargeStatus.processing, next_retry_at=now + CLAIM_WINDOW)
        .execution_options(synchronize_session=False)
    )
    if _rowcount(claimed) != 1:
        db.rollback()
        db.refresh(charge)
        return charge

    pm = db.get(TenantPaymentMethod, charge.payment_method_id)
    profile = db.query(TenantBillingProfile).filter_by(tenant_id=charge.tenant_id).one_or_none()
    provider_pm_id = pm.provider_payment_method_id if pm else ""
    customer_id = profile.provider_customer_id if profile else None
    amount = charge.amount
    key = charge.idempotency_key
    description = (
        "Auto-reload saldo kredit Aeos"
        if charge.purpose == ChargePurpose.auto_reload
        else "Perpanjangan langganan Aeos"
    )
    db.commit()  # tutup transaksi SEBELUM HTTP ke gateway

    try:
        adapter = get_adapter()
        result: ChargeResult | None = None
        if previous != ChargeStatus.pending:
            # Pernah dikirim (unknown/processing): rekonsiliasi dulu dengan
            # key yang SAMA -- tidak pernah key baru untuk percobaan ini.
            result = adapter.get_charge_by_reference(key)
        if result is None:
            result = adapter.charge_saved_method(
                provider_payment_method_id=provider_pm_id,
                customer_id=customer_id,
                amount=amount,
                reference_id=key,
                idempotency_key=key,
                description=description,
            )
    except (PaymentGatewayTimeout, HTTPException) as exc:
        logger.warning("Charge %s hasil tidak diketahui: %s", charge_id, type(exc).__name__)
        fresh = db.get(PaymentCharge, charge_id)
        assert fresh is not None
        fresh.status = ChargeStatus.unknown
        fresh.next_retry_at = now_utc() + UNKNOWN_RETRY
        fresh.failure_message = f"Hasil gateway tidak diketahui ({type(exc).__name__})"
        db.commit()
        return fresh
    return apply_charge_result(db, charge_id, result)


def apply_charge_result(db: Session, charge_id: UUID, result: ChargeResult) -> PaymentCharge:
    charge = db.get(PaymentCharge, charge_id)
    assert charge is not None
    if result.status == "succeeded":
        apply_charge_success(db, charge, provider_charge_id=result.provider_charge_id)
    elif result.status in ("failed", "requires_action"):
        # MIT yang meminta autentikasi ulang diperlakukan gagal (K12).
        code = result.failure_code or (
            "REQUIRES_ACTION" if result.status == "requires_action" else "FAILED"
        )
        apply_charge_failure(
            db,
            charge,
            code=code,
            message=result.failure_message,
            provider_charge_id=result.provider_charge_id,
        )
    else:
        charge.status = ChargeStatus.processing
        charge.provider_charge_id = charge.provider_charge_id or result.provider_charge_id
        charge.next_retry_at = now_utc() + PENDING_RECHECK
        db.commit()
    db.refresh(charge)
    return charge


def apply_charge_success(
    db: Session, charge: PaymentCharge, *, provider_charge_id: str | None
) -> bool:
    """Terapkan sukses tepat sekali (CAS status != succeeded). Commit."""
    previous = charge.status
    won = db.execute(
        update(PaymentCharge)
        .where(PaymentCharge.id == charge.id, PaymentCharge.status != ChargeStatus.succeeded)
        .values(
            status=ChargeStatus.succeeded,
            completed_at=now_utc(),
            next_retry_at=None,
            provider_charge_id=provider_charge_id or charge.provider_charge_id,
        )
        .execution_options(synchronize_session=False)
    )
    if _rowcount(won) != 1:
        db.rollback()
        return False
    db.refresh(charge)
    if previous == ChargeStatus.failed:
        audit_add(
            db,
            action="billing.charge_late_success",
            entity_type="payment_charge",
            entity_id=charge.id,
            detail={"purpose": charge.purpose.value},
            tenant_id=charge.tenant_id,
        )
    if charge.purpose == ChargePurpose.auto_reload:
        from app.modules.billing import auto_reload

        auto_reload.on_charge_success(db, charge)
    else:
        from app.modules.billing import renewal

        renewal.on_charge_success(db, charge)
    db.commit()
    return True


def apply_charge_failure(
    db: Session,
    charge: PaymentCharge,
    *,
    code: str,
    message: str | None,
    provider_charge_id: str | None = None,
) -> bool:
    """Terapkan gagal tepat sekali; status terminal tidak ditimpa. Commit."""
    won = db.execute(
        update(PaymentCharge)
        .where(
            PaymentCharge.id == charge.id,
            or_(
                PaymentCharge.status.in_(
                    [
                        ChargeStatus.pending,
                        ChargeStatus.processing,
                        ChargeStatus.unknown,
                        ChargeStatus.requires_action,
                    ]
                )
            ),
        )
        .values(
            status=ChargeStatus.failed,
            completed_at=now_utc(),
            next_retry_at=None,
            failure_code=code[:80],
            failure_message=(message or "")[:300] or None,
            provider_charge_id=provider_charge_id or charge.provider_charge_id,
        )
        .execution_options(synchronize_session=False)
    )
    if _rowcount(won) != 1:
        db.rollback()
        return False
    db.refresh(charge)
    if charge.purpose == ChargePurpose.auto_reload:
        from app.modules.billing import auto_reload

        auto_reload.on_charge_failure(db, charge, code)
    else:
        from app.modules.billing import renewal

        renewal.on_charge_failure(db, charge, code)
    db.commit()
    return True
