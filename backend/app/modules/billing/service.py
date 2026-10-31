import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.money import round_rupiah, to_decimal
from app.core.tenancy import get_request_meta, get_requester_user, get_tenant
from app.modules.billing.models import (
    AUTO_RELOAD_AMOUNT_IDR,
    TIER_MONTHLY_FEE_IDR,
    BillingPeriod,
    CreditTransaction,
    CreditTransactionType,
    PaymentMethodStatus,
    SubscriptionStatus,
    SubscriptionTier,
    TenantBudgetCycle,
    TenantCreditAccount,
    TenantPaymentMethod,
    TenantSubscription,
)

logger = logging.getLogger(__name__)

METERED_BLOCKED_CODE = "metered_blocked"
SUBSCRIPTION_PAST_DUE_CODE = "subscription_past_due"
# Pipeline AI yang dipicu pihak ketiga (kandidat AI Interview) tidak diblokir
# di tengah jalan saat saldo habis (keputusan K7) -- sesi baru ditolak di
# titik pembuatan undangan, bukan di tiap panggilan LLM.
METERED_EXEMPT_AI_FEATURE_PREFIXES = ("ai_interview",)


# ---------------------------------------------------------------------------
# Utilitas bersama modul billing
# ---------------------------------------------------------------------------


def audit_add(
    db: Session,
    *,
    action: str,
    entity_type: str | None = None,
    entity_id: UUID | str | None = None,
    detail: dict | None = None,
    tenant_id: UUID | None = None,
) -> None:
    """Catat audit TANPA commit -- ikut transaksi efek bisnisnya.

    `audit.service.log_event` sengaja commit sendiri (dan rollback seluruh
    sesi bila gagal), yang akan mematahkan atomisitas webhook/charge. Di
    modul billing, log audit harus tersimpan bersama efeknya atau tidak sama
    sekali. `detail` TIDAK BOLEH berisi token/PAN/payload mentah.
    """
    from app.modules.audit.models import AuditLog

    ip, agent = get_request_meta()
    resolved_entity: UUID | None = None
    if entity_id is not None:
        try:
            resolved_entity = entity_id if isinstance(entity_id, UUID) else UUID(str(entity_id))
        except ValueError:
            resolved_entity = None
    db.add(
        AuditLog(
            action=action,
            tenant_id=tenant_id if tenant_id is not None else get_tenant(),
            user_id=get_requester_user(),
            entity_type=entity_type,
            entity_id=resolved_entity,
            ip=ip,
            user_agent=agent,
            detail_json=json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
        )
    )


def notify_billing_users(db: Session, tenant_id: UUID, *, title: str, body: str) -> None:
    """Notifikasi in-app ke admin/finance/management aktif tenant -- TANPA
    commit (beda dari `notifications.service.notify` yang commit sendiri)."""
    from app.modules.auth.models import User, UserRole
    from app.modules.notifications.models import Notification

    recipients = (
        db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.role.in_([UserRole.admin, UserRole.finance, UserRole.management]),
            )
        )
        .scalars()
        .all()
    )
    for uid in recipients:
        db.add(
            Notification(
                tenant_id=tenant_id,
                user_id=uid,
                title=title[:200],
                body=body[:500],
                category="billing",
                entity_type="billing",
            )
        )


def now_utc() -> datetime:
    return datetime.now(UTC)


def as_aware(value: datetime | None) -> datetime | None:
    """SQLite mengembalikan datetime naive walau kolom timezone=True."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Langganan & harga
# ---------------------------------------------------------------------------


def current_subscription(db: Session, tenant_id: UUID) -> TenantSubscription | None:
    """Baris langganan "berlaku" (aktif ATAU menunggak), terbaru dulu."""
    return (
        db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .where(
                TenantSubscription.status.in_(
                    [SubscriptionStatus.active, SubscriptionStatus.past_due]
                )
            )
            .order_by(TenantSubscription.started_at.desc())
        )
        .scalars()
        .first()
    )


def _period_lapsed(sub: TenantSubscription, today: date | None = None) -> bool:
    """True bila masa bayar lewat batas toleransi (hanya saat penegakan aktif)."""
    settings = get_settings()
    if not settings.billing_renewal_enforcement or sub.current_period_end is None:
        return False
    today = today or date.today()
    tolerance = settings.billing_renewal_grace_days + settings.billing_renewal_processing_days
    return today > sub.current_period_end + timedelta(days=tolerance)


def has_active_subscription(db: Session, tenant_id: UUID | None) -> bool:
    """True bila tenant punya `TenantSubscription` berstatus aktif dan masa
    bayarnya belum lewat (Opsi G). Murni baca DB -- tanpa panggilan gateway.

    Menggantikan `platform/service.py::is_licensed()` yang per-app_key --
    Opsi G satu tenant satu status langganan, bukan satu per SKU.
    """
    if tenant_id is None:
        return False
    sub = current_subscription(db, tenant_id)
    if sub is None or sub.status != SubscriptionStatus.active:
        return False
    return not _period_lapsed(sub)


def subscription_access(db: Session, tenant_id: UUID) -> str:
    """'active' | 'past_due' | 'none'. Bila masa bayar sudah lewat toleransi
    tapi cron renewal belum memprosesnya, baris ditandai `past_due` di sini
    (safety-net DB murni -- guard tidak pernah memanggil Xendit)."""
    sub = current_subscription(db, tenant_id)
    if sub is None:
        return "none"
    if sub.status == SubscriptionStatus.past_due:
        return "past_due"
    if _period_lapsed(sub):
        sub.status = SubscriptionStatus.past_due
        sub.past_due_since = sub.past_due_since or now_utc()
        audit_add(
            db,
            action="billing.subscription_past_due",
            entity_type="tenant_subscription",
            entity_id=sub.id,
            detail={"reason": "period_lapsed", "current_period_end": str(sub.current_period_end)},
            tenant_id=tenant_id,
        )
        db.commit()
        return "past_due"
    return "active"


def annual_discount_percent() -> Decimal | None:
    return get_settings().billing_annual_discount_percent


def price_for(tier: SubscriptionTier, period: BillingPeriod) -> tuple[Decimal, Decimal]:
    """(nominal per periode tagih, diskon %). Tahunan = 12 x bulanan x
    (1 - diskon), dibulatkan ke rupiah penuh. 422 bila tahunan belum
    dikonfigurasi (BILLING_ANNUAL_DISCOUNT_PERCENT kosong, keputusan K1)."""
    monthly = to_decimal(TIER_MONTHLY_FEE_IDR[tier])
    if period == BillingPeriod.monthly:
        return round_rupiah(monthly), Decimal(0)
    discount = annual_discount_percent()
    if discount is None:
        raise HTTPException(status_code=422, detail="Paket tahunan belum tersedia")
    fee = round_rupiah(monthly * 12 * (Decimal(100) - discount) / Decimal(100))
    return fee, discount


def list_plans() -> list[dict]:
    discount = annual_discount_percent()
    plans = []
    for tier in SubscriptionTier:
        monthly = round_rupiah(to_decimal(TIER_MONTHLY_FEE_IDR[tier]))
        annual: dict = {"available": discount is not None, "fee": None, "discount_percent": None}
        if discount is not None:
            fee, _ = price_for(tier, BillingPeriod.annual)
            annual = {
                "available": True,
                "fee": float(fee),
                "monthly_equivalent": float(round_rupiah(fee / 12)),
                "discount_percent": float(discount),
            }
        plans.append(
            {
                "tier": tier.value,
                "monthly_fee": float(monthly),
                "included_budget": float(monthly),
                "annual": annual,
            }
        )
    return plans


# ---------------------------------------------------------------------------
# Saldo
# ---------------------------------------------------------------------------

_WARNING_THRESHOLD_RATIO = 0.20


def get_balance_summary(db: Session, tenant_id: UUID) -> dict:
    """Ringkasan saldo untuk indikator topbar (Milestone 6) & halaman
    billing tenant (Milestone 7). State dihitung di server supaya frontend
    tidak menduplikasi ambang batas: `empty` bila total sisa <= 0, `warning`
    bila total sisa <= 20% dari total termasuk-langganan bulan ini, selain
    itu `normal`.
    """
    cycle = _get_open_cycle(db, tenant_id)
    account = _get_or_create_credit_account(db, tenant_id)

    cycle_included = float(cycle.included_budget) if cycle else 0.0
    cycle_remaining = cycle.remaining if cycle else 0.0
    credit_balance = float(account.balance)
    total_remaining = cycle_remaining + credit_balance

    if total_remaining <= 0:
        state = "empty"
    elif cycle_included > 0 and total_remaining <= cycle_included * _WARNING_THRESHOLD_RATIO:
        state = "warning"
    else:
        state = "normal"

    return {
        "cycle_remaining": cycle_remaining,
        "cycle_included": cycle_included,
        "credit_balance": credit_balance,
        "state": state,
    }


class InsufficientCreditError(Exception):
    """Sisa cycle + saldo top-up tenant tidak cukup menutup debit ini."""


def _get_open_cycle(db: Session, tenant_id: UUID) -> TenantBudgetCycle | None:
    return (
        db.execute(
            select(TenantBudgetCycle)
            .where(TenantBudgetCycle.tenant_id == tenant_id)
            .where(TenantBudgetCycle.closed_at.is_(None))
            .order_by(TenantBudgetCycle.period_start.desc())
        )
        .scalars()
        .first()
    )


def _get_or_create_credit_account(db: Session, tenant_id: UUID) -> TenantCreditAccount:
    account = db.execute(
        select(TenantCreditAccount).where(TenantCreditAccount.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if account is None:
        account = TenantCreditAccount(tenant_id=tenant_id, balance=0)
        db.add(account)
        db.flush()
    return account


def total_remaining(db: Session, tenant_id: UUID) -> float:
    cycle = _get_open_cycle(db, tenant_id)
    account = _get_or_create_credit_account(db, tenant_id)
    return (cycle.remaining if cycle else 0.0) + float(account.balance)


def default_payment_method(db: Session, account: TenantCreditAccount) -> TenantPaymentMethod | None:
    if account.default_payment_method_id is None:
        return None
    pm = db.get(TenantPaymentMethod, account.default_payment_method_id)
    if pm is None or pm.status != PaymentMethodStatus.active:
        return None
    return pm


# ---------------------------------------------------------------------------
# Auto-reload: preferensi
# ---------------------------------------------------------------------------


def get_auto_reload_settings(db: Session, tenant_id: UUID) -> dict:
    """Preferensi + status nyata auto-reload. `effective=false` bila belum
    ada metode bayar default aktif (auto-reload tidak akan pernah jalan)."""
    account = _get_or_create_credit_account(db, tenant_id)
    pm = default_payment_method(db, account)
    if not account.auto_reload_enabled:
        effective, reason = False, "disabled"
    elif pm is None:
        effective, reason = False, "no_payment_method"
    elif account.auto_reload_threshold is None:
        effective, reason = False, "no_threshold"
    else:
        effective, reason = True, None
    return {
        "enabled": account.auto_reload_enabled,
        "threshold": float(account.auto_reload_threshold)
        if account.auto_reload_threshold is not None
        else None,
        "amount": float(AUTO_RELOAD_AMOUNT_IDR),
        "effective": effective,
        "reason": reason,
        "failure_count": account.auto_reload_failure_count,
        "last_error": account.auto_reload_last_error,
        "next_attempt_at": account.auto_reload_next_attempt_at,
        "in_flight": account.auto_reload_in_flight_charge_id is not None,
    }


def update_auto_reload_settings(
    db: Session,
    tenant_id: UUID,
    *,
    enabled: bool,
    threshold: float | None,
) -> dict:
    """Simpan preferensi. Nominal reload TETAP Rp100.000 (K3) -- tidak
    menerima input. Mengaktifkan butuh metode bayar default aktif dan ambang
    (atau default env BILLING_AUTO_RELOAD_DEFAULT_THRESHOLD, K2).
    Mengaktifkan ulang mereset hitungan gagal (bertindak sebagai "coba lagi")."""
    account = _get_or_create_credit_account(db, tenant_id)
    if threshold is None and enabled:
        default_threshold = get_settings().billing_auto_reload_default_threshold
        threshold = float(default_threshold) if default_threshold is not None else None
    if enabled:
        if default_payment_method(db, account) is None:
            raise HTTPException(
                status_code=422,
                detail="Tambahkan metode bayar (kartu/GoPay) dan jadikan default dulu",
            )
        if threshold is None:
            raise HTTPException(status_code=422, detail="Ambang batas auto-reload wajib diisi")
    before = {
        "enabled": account.auto_reload_enabled,
        "threshold": float(account.auto_reload_threshold)
        if account.auto_reload_threshold is not None
        else None,
    }
    account.auto_reload_enabled = enabled
    account.auto_reload_threshold = threshold
    account.auto_reload_amount = float(AUTO_RELOAD_AMOUNT_IDR)
    if enabled:
        account.auto_reload_failure_count = 0
        account.auto_reload_next_attempt_at = None
    audit_add(
        db,
        action="billing.auto_reload_settings_changed",
        entity_type="tenant_credit_account",
        entity_id=account.id,
        detail={"before": before, "after": {"enabled": enabled, "threshold": threshold}},
        tenant_id=tenant_id,
    )
    db.commit()
    return get_auto_reload_settings(db, tenant_id)


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


def record_credit_transaction(
    db: Session,
    *,
    amount: float,
    ref_event: str,
    ref_entity_type: str | None = None,
    ref_entity_id: str | None = None,
    allow_negative: bool = False,
    tx_type: CreditTransactionType | None = None,
    receipt_id: UUID | None = None,
) -> list[CreditTransaction]:
    """Catat satu debit/kredit ke ledger tenant aktif (dari konteks
    `get_tenant()`, sama seperti pola `core/ai_usage.py::record_usage()`).

    `amount` negatif = debit (dipotong dari sisa `TenantBudgetCycle` dulu,
    baru `TenantCreditAccount.balance`; kalau satu debit melintasi dua
    sumber itu, dicatat sebagai DUA baris ledger -- masing-masing baris
    HARUS mencerminkan tepat satu sumber saldo yang dipotong supaya
    `balance_after` per baris tetap bisa direkonstruksi tanpa ambiguitas).
    `amount` positif = kredit (top-up/pembayaran langganan) ke saldo top-up;
    `tx_type` membedakan top-up manual vs auto-reload (default manual),
    dan kredit apa pun mencabut penanda blokir metered.

    Tenant dengan billing bypass (`_is_billing_bypass` -- mode internal atau
    override per-tenant) tidak pernah didebit -- dikembalikan `[]` tanpa
    menyentuh ledger, konsisten dengan `require_active_subscription()` yang
    juga tidak menegakkan apa pun untuk tenant itu.

    `allow_negative=True` (dipakai cycle-close periodik, Milestone 3) tidak
    pernah menolak -- saldo top-up boleh negatif, direkonsiliasi lewat
    pembayaran berikutnya. Selain itu (event-based real-time) raise
    `InsufficientCreditError` kalau debit akan membuat saldo top-up
    negatif -- pemanggil (lihat `charge_metered_event`) menerjemahkan ini
    ke HTTPException(402) supaya aksi bertarif gagal-tertutup (fail-closed),
    tanpa mematahkan aksi non-metered lain tenant tersebut.

    Setelah debit diterapkan, pemicu auto-reload diperiksa (outbox di
    transaksi yang sama -- debit yang di-rollback ikut membatalkannya).
    """
    tenant_id = get_tenant()
    if tenant_id is None:
        return []

    from app.core.security import _is_billing_bypass

    if _is_billing_bypass(db, tenant_id):
        return []

    cycle = _get_open_cycle(db, tenant_id)
    account = _get_or_create_credit_account(db, tenant_id)
    rows: list[CreditTransaction] = []

    def _write(t: CreditTransactionType, tx_amount: float, rid: UUID | None = None) -> None:
        balance_after = float(account.balance) + (cycle.remaining if cycle else 0.0)
        tx = CreditTransaction(
            tenant_id=tenant_id,
            type=t,
            amount=tx_amount,
            ref_event=ref_event,
            ref_entity_type=ref_entity_type,
            ref_entity_id=ref_entity_id,
            balance_after=balance_after,
            receipt_id=rid,
        )
        db.add(tx)
        rows.append(tx)

    if amount >= 0:
        account.balance = float(account.balance) + amount
        _write(tx_type or CreditTransactionType.topup_manual, amount, receipt_id)
        if account.metered_blocked_at is not None:
            audit_add(
                db,
                action="billing.metered_unblocked",
                entity_type="tenant_credit_account",
                entity_id=account.id,
                detail={"trigger": ref_event},
                tenant_id=tenant_id,
            )
            account.metered_blocked_at = None
            account.metered_block_reason = None
    else:
        debit = -amount
        from_cycle = 0.0
        if cycle is not None and cycle.remaining > 0:
            from_cycle = min(debit, cycle.remaining)
            cycle.consumed = float(cycle.consumed) + from_cycle
            _write(CreditTransactionType.debit_cycle, -from_cycle)
        from_credit = debit - from_cycle
        if from_credit > 0:
            if not allow_negative and float(account.balance) - from_credit < 0:
                raise InsufficientCreditError(
                    f"Saldo tidak cukup untuk {ref_event} (butuh Rp{from_credit:,.0f})"
                )
            account.balance = float(account.balance) - from_credit
            _write(CreditTransactionType.debit_credit, -from_credit)

    db.flush()
    if amount < 0:
        from app.modules.billing import auto_reload

        auto_reload.maybe_enqueue(db, tenant_id, account, cycle)
    return rows


def charge_metered_event(
    db: Session,
    *,
    amount: float,
    ref_event: str,
    ref_entity_type: str | None = None,
    ref_entity_id: str | None = None,
) -> list[CreditTransaction]:
    """Debit real-time untuk satu aksi bertarif (match/invoice/faktur/AI).

    Selalu fail-closed: saldo habis -> HTTPException(402), aksi dibatalkan.
    Untuk debit periodik (cycle-close) pakai `record_credit_transaction`
    langsung dengan `allow_negative=True`, bukan fungsi ini. Auto-reload
    reaktif dijalankan lebih awal di `assert_metered_allowed` (sebelum aksi
    menulis apa pun), bukan di sini -- di titik ini sesi pemanggil sudah
    berisi tulisan yang belum di-commit, jadi tidak aman memanggil gateway.
    """
    try:
        return record_credit_transaction(
            db,
            amount=-abs(amount),
            ref_event=ref_event,
            ref_entity_type=ref_entity_type,
            ref_entity_id=ref_entity_id,
        )
    except InsufficientCreditError as exc:
        raise HTTPException(
            status_code=402, detail=str(exc), headers={"X-Error-Code": METERED_BLOCKED_CODE}
        ) from exc


def _metered_blocked_error(reason: str | None) -> HTTPException:
    message = "Saldo kredit habis -- fitur berbayar diblokir. Top up atau perbarui metode bayar."
    if reason == "auto_reload_failed":
        message = (
            "Auto-reload gagal -- fitur berbayar diblokir. Data tetap bisa diakses. "
            "Top up atau perbarui metode bayar di halaman Pembayaran."
        )
    return HTTPException(
        status_code=402, detail=message, headers={"X-Error-Code": METERED_BLOCKED_CODE}
    )


def assert_metered_allowed(db: Session, amount: float = 0, *, reactive: bool = True) -> None:
    """Gerbang fitur metered (aturan gagal bayar (e)): 402 bila sisa saldo
    (jatah siklus + top-up) tidak menutup `amount` (atau <= 0 bila amount 0).

    Dipanggil di AWAL aksi metered, sebelum aksi menulis apa pun. Bila
    saldo kurang dan auto-reload memenuhi syarat, satu percobaan auto-reload
    sinkron dijalankan (jalur reaktif, PRD §4.4.4: siklus -> saldo ->
    auto-reload -> blokir) -- hanya bila sesi belum berisi tulisan yang
    tertunda, karena transaksi harus ditutup sebelum memanggil gateway.
    Tenant billing bypass tidak pernah diblokir.
    """
    tenant_id = get_tenant()
    if tenant_id is None:
        return
    from app.core.security import _is_billing_bypass

    if _is_billing_bypass(db, tenant_id):
        return

    def _enough() -> bool:
        remaining = total_remaining(db, tenant_id)
        return remaining >= amount if amount > 0 else remaining > 0

    if _enough():
        return
    if reactive and not (db.new or db.dirty or db.deleted):
        from app.modules.billing import auto_reload

        if auto_reload.try_reactive_reload(db, tenant_id) and _enough():
            return
    account = _get_or_create_credit_account(db, tenant_id)
    raise _metered_blocked_error(account.metered_block_reason)


def assert_ai_allowed(feature: str | None) -> None:
    """Pre-check panggilan LLM -- satu-satunya cara memblokir AI karena debit
    `ai_usage` terjadi pasca-fakta (allow_negative). Sesi DB terpisah (pola
    `core/ai_usage.py`) karena banyak call site AI tidak punya `db`."""
    tenant_id = get_tenant()
    if tenant_id is None:
        return
    if feature and feature.startswith(METERED_EXEMPT_AI_FEATURE_PREFIXES):
        return
    from app.core import ai_usage

    db = ai_usage.SessionLocal()
    try:
        assert_metered_allowed(db, 0, reactive=False)
    finally:
        db.close()


def list_transactions(
    db: Session, tenant_id: UUID, *, limit: int = 50, offset: int = 0
) -> list[CreditTransaction]:
    """Riwayat transaksi ledger tenant, terbaru dulu (halaman billing Milestone 7)."""
    return list(
        db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.tenant_id == tenant_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


# ---------------------------------------------------------------------------
# Status untuk banner frontend
# ---------------------------------------------------------------------------


def get_billing_status(db: Session, tenant_id: UUID) -> dict:
    """Ringkasan status penagihan untuk banner (`GET /billing/status`).
    Murni baca DB (kecuali penandaan past_due safety-net)."""
    from app.core.security import _is_billing_bypass

    bypass = _is_billing_bypass(db, tenant_id)
    access_state = "active" if bypass else subscription_access(db, tenant_id)
    sub = current_subscription(db, tenant_id)
    account = _get_or_create_credit_account(db, tenant_id)
    remaining = total_remaining(db, tenant_id)
    if access_state != "active":
        access, block_reason = (
            "none",
            (SUBSCRIPTION_PAST_DUE_CODE if access_state == "past_due" else "no_subscription"),
        )
    elif not bypass and remaining <= 0:
        access = "metered_blocked"
        block_reason = account.metered_block_reason or "balance_exhausted"
    else:
        access, block_reason = "full", None
    return {
        "billing_bypass": bypass,
        "subscription": {
            "id": str(sub.id),
            "tier": sub.tier.value,
            "status": sub.status.value,
            "billing_period": sub.billing_period.value,
            "period_fee": float(sub.period_fee) if sub.period_fee is not None else None,
            "discount_percent": float(sub.discount_percent or 0),
            "current_period_end": sub.current_period_end,
            "past_due_since": sub.past_due_since,
            "auto_renew": sub.auto_renew,
        }
        if sub
        else None,
        "access": access,
        "block_reason": block_reason,
        "total_remaining": remaining,
        "auto_reload": {
            "enabled": account.auto_reload_enabled,
            "failure_count": account.auto_reload_failure_count,
            "last_error": account.auto_reload_last_error,
        },
        "has_default_payment_method": default_payment_method(db, account) is not None,
        "renewal_enforcement": get_settings().billing_renewal_enforcement,
    }
