import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
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


class BillingPeriod(str, enum.Enum):
    monthly = "monthly"
    annual = "annual"


TIER_MONTHLY_FEE_IDR: dict[SubscriptionTier, float] = {
    SubscriptionTier.tier1: 500_000,
    SubscriptionTier.tier2: 2_000_000,
    SubscriptionTier.tier3: 5_000_000,
}

# Nominal auto-reload tetap (PRD §4.4.1, keputusan K3): tidak bisa diubah tenant.
AUTO_RELOAD_AMOUNT_IDR = Decimal("100000")


def _period_fee_default(context) -> object:
    """Default `period_fee` = `monthly_fee` bila pemanggil lama (seed test,
    skrip migrasi Fase 28) tidak mengisinya -- paket bulanan memang
    period_fee == monthly_fee."""
    return context.get_current_parameters().get("monthly_fee")


class TenantSubscription(TenantMixin, Base):
    """Langganan tier Opsi G milik satu tenant (Fase 28).

    Satu tenant hanya boleh punya satu baris berstatus `active`/`past_due`
    pada satu waktu -- ditegakkan di service layer (bukan partial-unique
    constraint, supaya portabel lintas SQLite/Postgres, sama seperti alasan
    `uq_license_tenant_app` di Opsi F tidak dibuat partial).

    `current_period_end` = tanggal terakhir masa yang SUDAH dibayar. NULL
    berarti baris legacy/override platform (pembayaran di luar sistem) --
    tidak pernah dikunci oleh penegakan renewal. Jatah saldo
    (`TenantBudgetCycle`) tetap bulanan walau `billing_period=annual`.
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
    billing_period: Mapped[BillingPeriod] = mapped_column(
        Enum(BillingPeriod, native_enum=False, length=20),
        default=BillingPeriod.monthly,
        server_default=BillingPeriod.monthly.value,
    )
    period_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=_period_fee_default)
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal(0), server_default="0"
    )
    current_period_end: Mapped[date | None] = mapped_column(Date(), default=None)
    past_due_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    renewal_attempt_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    next_renewal_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


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


class TenantBillingProfile(TenantMixin, Base):
    """Identitas pembeli (tenant) untuk kwitansi + ID customer Xendit."""

    __tablename__ = "tenant_billing_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_billing_profile_tenant"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    legal_name: Mapped[str] = mapped_column(String(255))
    npwp: Mapped[str | None] = mapped_column(String(22), default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    billing_email: Mapped[str | None] = mapped_column(String(255), default=None)
    provider_customer_id: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaymentMethodType(str, enum.Enum):
    card = "card"
    gopay = "gopay"


class PaymentMethodStatus(str, enum.Enum):
    pending_activation = "pending_activation"
    active = "active"
    failed = "failed"
    expired = "expired"
    removed = "removed"


class TenantPaymentMethod(TenantMixin, Base):
    """Metode bayar tersimpan (token kartu / GoPay linked) milik tenant.

    HANYA berisi ID/token dari gateway + metadata tampilan yang aman
    (brand, 4 digit terakhir, masa berlaku, nomor e-wallet yang sudah
    disamarkan gateway). TIDAK PERNAH ada kolom PAN/nomor kartu/CVV --
    dijaga `tests/test_billing_payment_methods.py` (regresi skema).
    """

    __tablename__ = "tenant_payment_methods"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_payment_method_id", name="uq_payment_method_provider_id"
        ),
        UniqueConstraint("reference_id", name="uq_payment_method_reference"),
        Index("ix_payment_method_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    provider_payment_method_id: Mapped[str] = mapped_column(String(120))
    reference_id: Mapped[str] = mapped_column(String(160))
    type: Mapped[PaymentMethodType] = mapped_column(
        Enum(PaymentMethodType, native_enum=False, length=20)
    )
    status: Mapped[PaymentMethodStatus] = mapped_column(
        Enum(PaymentMethodStatus, native_enum=False, length=30),
        default=PaymentMethodStatus.pending_activation,
    )
    card_brand: Mapped[str | None] = mapped_column(String(30), default=None)
    card_last4: Mapped[str | None] = mapped_column(String(4), default=None)
    card_exp_month: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    card_exp_year: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    ewallet_account_masked: Mapped[str | None] = mapped_column(String(40), default=None)
    failure_reason: Mapped[str | None] = mapped_column(String(200), default=None)
    created_by: Mapped[UUID | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TenantCreditAccount(TenantMixin, Base):
    """Saldo top-up tenant -- TIDAK direset per siklus (beda dari
    `TenantBudgetCycle`, yang jatah bulanannya reset).

    Auto-reload (Fase 28 lanjutan): `auto_reload_in_flight_charge_id` adalah
    kunci compare-and-set -- paling banyak satu charge auto-reload berjalan
    per tenant (lihat `billing/auto_reload.py`). `metered_blocked_at`
    mencatat KENAPA fitur metered terblokir (auto-reload gagal); blokir
    efektifnya sendiri dihitung dari sisa saldo (lihat
    `service.assert_metered_allowed`).
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
    default_payment_method_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant_payment_methods.id"), default=None
    )
    auto_reload_in_flight_charge_id: Mapped[UUID | None] = mapped_column(default=None)
    auto_reload_failure_count: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0"
    )
    auto_reload_next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    auto_reload_last_error: Mapped[str | None] = mapped_column(String(200), default=None)
    metered_blocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    metered_block_reason: Mapped[str | None] = mapped_column(String(40), default=None)


class CreditTransactionType(str, enum.Enum):
    debit_cycle = "debit_cycle"
    debit_credit = "debit_credit"
    topup_manual = "topup_manual"
    topup_auto_reload = "topup_auto_reload"
    subscription_charge = "subscription_charge"
    subscription_renewal = "subscription_renewal"


class CreditTransaction(TenantMixin, Base):
    """Baris ledger tunggal -- setiap debit/kredit saldo tercatat di sini.

    `amount` negatif = debit (pemakaian), positif = kredit (top-up/langganan
    dibayar). `balance_after` adalah snapshot gabungan sisa-cycle + saldo
    top-up TEPAT setelah transaksi ini diterapkan, untuk kebutuhan audit
    tanpa perlu rekonstruksi ulang dari histori. `receipt_id` diisi di
    transaksi yang sama saat baris kredit hasil pembayaran dibuat.
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
    receipt_id: Mapped[UUID | None] = mapped_column(ForeignKey("billing_receipts.id"), default=None)


class PaymentIntentType(str, enum.Enum):
    subscription = "subscription"
    topup = "topup"
    renewal = "renewal"


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
    apa pun soal model bisnis Opsi G. `billing_period`/`discount_percent`
    adalah snapshot harga saat checkout (perubahan env sesudahnya tidak
    mengubah kontrak yang sudah dibayar).
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
    billing_period: Mapped[str | None] = mapped_column(String(20), default=None)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    subscription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant_subscriptions.id"), default=None
    )
    # Disimpan agar invoice pending (mis. renewal) bisa dibuka ulang tanpa
    # menerbitkan invoice kedua yang berisiko terbayar dobel.
    checkout_url: Mapped[str | None] = mapped_column(String(500), default=None)


class ChargePurpose(str, enum.Enum):
    auto_reload = "auto_reload"
    renewal = "renewal"


class ChargeStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    requires_action = "requires_action"
    succeeded = "succeeded"
    failed = "failed"
    # Timeout/5xx gateway -- WAJIB direkonsiliasi (get by reference) dengan
    # idempotency key yang SAMA sebelum dicoba lagi, tidak pernah key baru.
    unknown = "unknown"


class PaymentCharge(TenantMixin, Base):
    """Charge merchant-initiated memakai metode bayar tersimpan (auto-reload
    & renewal). `idempotency_key` sekaligus `reference_id` di gateway."""

    __tablename__ = "payment_charges"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payment_charge_idem"),
        UniqueConstraint("provider_charge_id", name="uq_payment_charge_provider"),
        Index("ix_payment_charge_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    purpose: Mapped[ChargePurpose] = mapped_column(
        Enum(ChargePurpose, native_enum=False, length=20)
    )
    payment_method_id: Mapped[UUID] = mapped_column(ForeignKey("tenant_payment_methods.id"))
    subscription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant_subscriptions.id"), default=None
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    provider_charge_id: Mapped[str | None] = mapped_column(String(120), default=None)
    status: Mapped[ChargeStatus] = mapped_column(
        Enum(ChargeStatus, native_enum=False, length=20), default=ChargeStatus.pending
    )
    attempt_no: Mapped[int] = mapped_column(SmallInteger, default=1)
    failure_code: Mapped[str | None] = mapped_column(String(80), default=None)
    failure_message: Mapped[str | None] = mapped_column(String(300), default=None)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ReceiptSource(str, enum.Enum):
    payment_intent = "payment_intent"
    payment_charge = "payment_charge"


class BillingReceipt(TenantMixin, Base):
    """Kwitansi resmi Aeos (penjual SaaS) untuk satu pembayaran berhasil.

    Dibuat SEKALI di transaksi yang sama dengan efek pembayaran: nomor &
    snapshot penjual/pembeli/rincian dikunci saat itu. PDF dirender
    deterministik dari snapshot saat pertama diminta lalu disimpan --
    `pdf_object_key` tidak pernah diubah sesudahnya (immutable).
    """

    __tablename__ = "billing_receipts"
    __table_args__ = (
        UniqueConstraint("receipt_number", name="uq_receipt_number"),
        UniqueConstraint("receipt_year", "sequence_no", name="uq_receipt_year_seq"),
        UniqueConstraint("payment_intent_id", name="uq_receipt_intent"),
        UniqueConstraint("payment_charge_id", name="uq_receipt_charge"),
        Index("ix_receipt_tenant_issued", "tenant_id", "issued_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_number: Mapped[str] = mapped_column(String(40))
    receipt_year: Mapped[int] = mapped_column(SmallInteger)
    sequence_no: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[ReceiptSource] = mapped_column(
        Enum(ReceiptSource, native_enum=False, length=20)
    )
    payment_intent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_intents.id"), default=None
    )
    payment_charge_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_charges.id"), default=None
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # NULL = identitas penjual belum dikonfigurasi saat terbit (K8) --
    # diisi & dibekukan saat render pertama setelah env diisi.
    seller_snapshot_json: Mapped[str | None] = mapped_column(Text, default=None)
    buyer_snapshot_json: Mapped[str] = mapped_column(Text)
    lines_json: Mapped[str] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    dpp: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    ppn_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal(0))
    ppn_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal(0))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_method_label: Mapped[str] = mapped_column(String(80))
    provider_reference: Mapped[str | None] = mapped_column(String(120), default=None)
    pdf_object_key: Mapped[str | None] = mapped_column(String(500), default=None)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingReceiptSequence(Base):
    """Penomoran kwitansi platform-level (TANPA TenantMixin): penjualnya satu
    (Aeos), jadi nomor wajib berurutan LINTAS semua tenant per tahun.
    Tidak berisi data bisnis tenant -- tidak tersentuh filter ORM/RLS."""

    __tablename__ = "billing_receipt_sequences"

    year: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    last_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class WebhookEventStatus(str, enum.Enum):
    received = "received"
    processed = "processed"
    ignored = "ignored"
    failed = "failed"


class PaymentWebhookEvent(Base):
    """Jejak + dedup event webhook gateway (platform-level, TANPA TenantMixin).

    Event diterima SEBELUM tenant diketahui, dan sebagian tidak pernah
    terpetakan ke tenant mana pun -- `tenant_id` nullable hanya untuk
    forensik (pola sama `audit_logs`). Diakses hanya dari webhook dan
    `/platform/*`.
    """

    __tablename__ = "payment_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "dedup_key", name="uq_webhook_event_dedup"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    dedup_key: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str | None] = mapped_column(String(120), default=None)
    tenant_id: Mapped[UUID | None] = mapped_column(default=None)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[WebhookEventStatus] = mapped_column(
        Enum(WebhookEventStatus, native_enum=False, length=20),
        default=WebhookEventStatus.received,
    )
    error: Mapped[str | None] = mapped_column(String(300), default=None)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
