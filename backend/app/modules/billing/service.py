from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import get_tenant
from app.modules.billing.models import (
    CreditTransaction,
    CreditTransactionType,
    SubscriptionStatus,
    TenantBudgetCycle,
    TenantCreditAccount,
    TenantSubscription,
)


def has_active_subscription(db: Session, tenant_id: UUID | None) -> bool:
    """True bila tenant punya `TenantSubscription` berstatus aktif (Opsi G).

    Menggantikan `platform/service.py::is_licensed()` yang per-app_key --
    Opsi G satu tenant satu status langganan, bukan satu per SKU.
    """
    if tenant_id is None:
        return False
    row = db.execute(
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
        .where(TenantSubscription.status == SubscriptionStatus.active)
    ).scalar_one_or_none()
    return row is not None


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


def record_credit_transaction(
    db: Session,
    *,
    amount: float,
    ref_event: str,
    ref_entity_type: str | None = None,
    ref_entity_id: str | None = None,
    allow_negative: bool = False,
) -> list[CreditTransaction]:
    """Catat satu debit/kredit ke ledger tenant aktif (dari konteks
    `get_tenant()`, sama seperti pola `core/ai_usage.py::record_usage()`).

    `amount` negatif = debit (dipotong dari sisa `TenantBudgetCycle` dulu,
    baru `TenantCreditAccount.balance`; kalau satu debit melintasi dua
    sumber itu, dicatat sebagai DUA baris ledger -- masing-masing baris
    HARUS mencerminkan tepat satu sumber saldo yang dipotong supaya
    `balance_after` per baris tetap bisa direkonstruksi tanpa ambiguitas).
    `amount` positif = kredit (top-up/pembayaran langganan) ke saldo top-up.

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

    def _write(tx_type: CreditTransactionType, tx_amount: float) -> None:
        balance_after = float(account.balance) + (cycle.remaining if cycle else 0.0)
        tx = CreditTransaction(
            tenant_id=tenant_id,
            type=tx_type,
            amount=tx_amount,
            ref_event=ref_event,
            ref_entity_type=ref_entity_type,
            ref_entity_id=ref_entity_id,
            balance_after=balance_after,
        )
        db.add(tx)
        rows.append(tx)

    if amount >= 0:
        account.balance = float(account.balance) + amount
        _write(CreditTransactionType.topup_manual, amount)
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
    langsung dengan `allow_negative=True`, bukan fungsi ini.
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
        raise HTTPException(status_code=402, detail=str(exc)) from exc


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
