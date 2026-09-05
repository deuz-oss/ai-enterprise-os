import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tenancy import TenantMixin


class SubscriptionTier(str, enum.Enum):
    tier1 = "tier1"
    tier2 = "tier2"
    tier3 = "tier3"


class SubscriptionStatus(str, enum.Enum):
    active = "aktif"
    past_due = "menunggak"
    cancelled = "dibatalkan"


TIER_MONTHLY_FEE_IDR: dict[SubscriptionTier, float] = {
    SubscriptionTier.tier1: 500_000,
    SubscriptionTier.tier2: 2_000_000,
    SubscriptionTier.tier3: 5_000_000,
}


class TenantSubscription(TenantMixin, Base):
    """Langganan tier Opsi G milik satu tenant (Fase 28).

    Satu tenant hanya boleh punya satu baris berstatus `active` pada satu
    waktu -- ditegakkan di service layer (bukan partial-unique constraint,
    supaya portabel lintas SQLite/Postgres, sama seperti alasan
    `uq_license_tenant_app` di Opsi F tidak dibuat partial).
    """

    __tablename__ = "tenant_subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, native_enum=False, length=20)
    )
    monthly_fee: Mapped[float] = mapped_column(Numeric(14, 2))
    included_budget: Mapped[float] = mapped_column(Numeric(14, 2))
    cycle_start_day: Mapped[int] = mapped_column(default=1)
    auto_renew: Mapped[bool] = mapped_column(default=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, length=20),
        default=SubscriptionStatus.active,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TenantBudgetCycle(TenantMixin, Base):
    """Satu periode (biasanya sebulan) dari saldo termasuk-langganan.

    `consumed` bertambah tiap ada debit event-based/periodik yang dipotong
    dari jalur cycle (bukan jalur saldo top-up) -- lihat
    `billing/service.py::record_credit_transaction`. `remaining` bukan
    kolom, dihitung `included_budget - consumed` di properti Python supaya
    tidak ada dua sumber kebenaran.
    """

    __tablename__ = "tenant_budget_cycles"
    __table_args__ = (Index("ix_budget_cycle_tenant_period", "tenant_id", "period_start"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    subscription_id: Mapped[UUID] = mapped_column(ForeignKey("tenant_subscriptions.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date())
    period_end: Mapped[date] = mapped_column(Date())
    included_budget: Mapped[float] = mapped_column(Numeric(14, 2))
    consumed: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def remaining(self) -> float:
        return float(self.included_budget) - float(self.consumed)


class TenantCreditAccount(TenantMixin, Base):
    """Saldo top-up tenant -- TIDAK direset per siklus (beda dari
    `TenantBudgetCycle`, yang jatah bulanannya reset). Kolom
    `auto_reload_*` disiapkan skemanya sekarang; logic auto-reload
    (kartu/GoPay tokenized) ditunda ke fase berikutnya per keputusan user
    saat perencanaan Fase 28 -- lihat plan file.
    """

    __tablename__ = "tenant_credit_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_credit_account_tenant"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    auto_reload_enabled: Mapped[bool] = mapped_column(default=False)
    auto_reload_threshold: Mapped[float | None] = mapped_column(Numeric(14, 2), default=None)
    auto_reload_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=100_000)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreditTransactionType(str, enum.Enum):
    debit_cycle = "debit_cycle"
    debit_credit = "debit_credit"
    topup_manual = "topup_manual"
    topup_auto_reload = "topup_auto_reload"
    subscription_charge = "subscription_charge"


class CreditTransaction(TenantMixin, Base):
    """Baris ledger tunggal -- setiap debit/kredit saldo tercatat di sini.

    `amount` negatif = debit (pemakaian), positif = kredit (top-up/langganan
    dibayar). `balance_after` adalah snapshot gabungan sisa-cycle + saldo
    top-up TEPAT setelah transaksi ini diterapkan, untuk kebutuhan audit
    tanpa perlu rekonstruksi ulang dari histori.
    """

    __tablename__ = "credit_transactions"
    __table_args__ = (Index("ix_credit_tx_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[CreditTransactionType] = mapped_column(
        Enum(CreditTransactionType, native_enum=False, length=30), index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    ref_event: Mapped[str] = mapped_column(String(80))
    ref_entity_type: Mapped[str | None] = mapped_column(String(50), default=None)
    ref_entity_id: Mapped[str | None] = mapped_column(String(100), default=None)
    balance_after: Mapped[float] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentIntentType(str, enum.Enum):
    subscription = "subscription"
    topup = "topup"


class PaymentIntentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    expired = "expired"
    failed = "failed"


class PaymentIntent(TenantMixin, Base):
    """Jembatan antara checkout Xendit dan efek bisnisnya.

    Dibuat saat tenant memilih tier / top-up (self-service, Milestone 7)
    lewat `billing/payment_service.py::create_checkout_intent`, ditutup saat
    webhook Xendit masuk (`billing/payment_service.py::reconcile_payment`) --
    `provider_invoice_id` adalah kunci pencarian dari payload webhook balik
    ke tenant/tier/jumlah yang relevan, karena Xendit sendiri tidak tahu
    apa pun soal model bisnis Opsi G.
    """

    __tablename__ = "payment_intents"
    __table_args__ = (UniqueConstraint("provider_invoice_id", name="uq_payment_intent_invoice"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[PaymentIntentType] = mapped_column(
        Enum(PaymentIntentType, native_enum=False, length=20)
    )
    tier: Mapped[SubscriptionTier | None] = mapped_column(
        Enum(SubscriptionTier, native_enum=False, length=20), default=None
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    provider_invoice_id: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[PaymentIntentStatus] = mapped_column(
        Enum(PaymentIntentStatus, native_enum=False, length=20),
        default=PaymentIntentStatus.pending,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
