"""Kontrak antarmuka adapter gateway pembayaran (Fase 28, Opsi G).

Mirror persis pola `core/esign/base.py`: semua provider (Xendit, sandbox)
mengembalikan struktur yang sama sehingga modul billing tidak perlu tahu
detail vendor.

Fase 28 lanjutan menambah metode bayar tersimpan (token kartu/GoPay),
charge merchant-initiated, dan normalisasi webhook. ATURAN KERAS: tidak ada
struktur di sini yang membawa nomor kartu (PAN) atau CVV -- kartu
ditokenisasi di browser (Xendit.js), backend hanya menerima `token_id`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class CheckoutResult:
    """Hasil pembuatan invoice/checkout di penyedia pembayaran."""

    provider_invoice_id: str
    checkout_url: str | None  # link hosted checkout untuk tenant


@dataclass(frozen=True)
class PaymentStatus:
    """Status pembayaran dari sudut pandang penyedia."""

    status: str  # pending | paid | expired | failed
    paid_at: str | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class CustomerResult:
    provider_customer_id: str


@dataclass(frozen=True)
class Action:
    """Langkah lanjutan yang harus dilakukan pengguna (3DS, linking GoPay)."""

    kind: str  # redirect | otp | deeplink
    url: str


@dataclass(frozen=True)
class PaymentMethodDisplay:
    """Metadata tampilan AMAN -- hanya yang dikembalikan gateway."""

    card_brand: str | None = None
    card_last4: str | None = None
    card_exp_month: int | None = None
    card_exp_year: int | None = None
    ewallet_account_masked: str | None = None


@dataclass(frozen=True)
class PaymentMethodResult:
    provider_payment_method_id: str
    # pending_activation | active | failed | expired
    status: str
    actions: list[Action] = field(default_factory=list)
    display: PaymentMethodDisplay = field(default_factory=PaymentMethodDisplay)
    failure_reason: str | None = None


@dataclass(frozen=True)
class ChargeResult:
    provider_charge_id: str | None
    # succeeded | pending | requires_action | failed
    status: str
    failure_code: str | None = None
    failure_message: str | None = None
    paid_at: str | None = None


@dataclass(frozen=True)
class WebhookEvent:
    """Event webhook yang sudah dinormalisasi lintas produk gateway."""

    dedup_key: str
    # invoice.paid | invoice.expired | payment.succeeded | payment.failed |
    # payment.pending | payment_method.activated | payment_method.expired |
    # payment_method.failed | unknown
    event_type: str
    object_id: str | None
    reference_id: str | None
    status: str
    paid_at: str | None = None
    failure_code: str | None = None
    payment_channel_label: str | None = None
    display: PaymentMethodDisplay = field(default_factory=PaymentMethodDisplay)


class PaymentGatewayTimeout(Exception):
    """Timeout/5xx saat charge -- hasil di gateway TIDAK diketahui. Pemanggil
    wajib menandai charge `unknown` dan merekonsiliasi dengan reference/
    idempotency key yang sama, bukan membuat key baru."""


_STATUS_INVOICE = {"PAID": "paid", "SETTLED": "paid", "EXPIRED": "expired"}
_PAYMENT_EVENT_STATUS = {
    "SUCCEEDED": "succeeded",
    "FAILED": "failed",
    "PENDING": "pending",
    "REQUIRES_ACTION": "requires_action",
}
_PM_STATUS = {
    "ACTIVE": "active",
    "REQUIRES_ACTION": "pending_activation",
    "PENDING": "pending_activation",
    "EXPIRED": "expired",
    "INACTIVE": "expired",
    "FAILED": "failed",
}
_DIGITS = re.compile(r"\d")


def extract_display(data: dict) -> PaymentMethodDisplay:
    """Ambil metadata tampilan dari objek payment method gateway dengan
    ALLOWLIST field (bukan blocklist). 4 digit terakhir diambil dari nomor
    yang SUDAH disamarkan gateway (`masked_card_number`), bukan PAN.

    TODO verifikasi Xendit: nama field persis `card.card_information`
    (`masked_card_number`, `expiry_month`, `expiry_year`, `network`) dan
    `ewallet.account.account_details` di Payment Methods API v2/v3.
    """
    card = data.get("card") or {}
    info = card.get("card_information") or card
    brand = info.get("network") or info.get("brand")
    masked = str(info.get("masked_card_number") or "")
    last4 = masked[-4:] if len(masked) >= 4 and _DIGITS.search(masked[-4:]) else None

    def _int(v: object) -> int | None:
        try:
            return int(str(v)) if v not in (None, "") else None
        except ValueError:
            return None

    ewallet = data.get("ewallet") or {}
    account = ewallet.get("account") or {}
    masked_wallet = account.get("account_details")
    return PaymentMethodDisplay(
        card_brand=str(brand)[:30] if brand else None,
        card_last4=last4,
        card_exp_month=_int(info.get("expiry_month")),
        card_exp_year=_int(info.get("expiry_year")),
        ewallet_account_masked=str(masked_wallet)[:40] if masked_wallet else None,
    )


def normalize_pm_status(vendor_status: str | None) -> str:
    return _PM_STATUS.get(str(vendor_status or "").upper(), "pending_activation")


def normalize_charge_status(vendor_status: str | None) -> str:
    return _PAYMENT_EVENT_STATUS.get(str(vendor_status or "").upper(), "pending")


def parse_xendit_style_webhook(headers: dict[str, str], payload: dict) -> WebhookEvent:
    """Normalisasi payload callback berformat Xendit (dipakai adapter Xendit
    DAN sandbox -- sandbox sengaja meniru bentuk payload Xendit).

    Dua bentuk yang dikenali:
    1. Callback Invoice (`/v2/invoices`) -- tanpa field `event`, field
       `id`/`external_id`/`status` di root.
    2. Webhook berbasis event (`{"event": "...", "data": {...}}`) untuk
       Payment Request & Payment Method.

    TODO verifikasi Xendit: nama event persis (`payment.succeeded`,
    `payment_method.activated`, ...) dan apakah header `webhook-id` dikirim
    untuk dedup; bila tidak, fallback `{event}:{object}:{status}`.
    """
    lowered = {k.lower(): v for k, v in headers.items()}
    event_name = payload.get("event")
    if not event_name:
        vendor_status = str(payload.get("status") or "").upper()
        mapped = _STATUS_INVOICE.get(vendor_status, vendor_status.lower() or "unknown")
        object_id = str(payload.get("id") or payload.get("external_id") or "").strip() or None
        event_type = f"invoice.{mapped}" if mapped in ("paid", "expired") else "unknown"
        channel = payload.get("payment_channel") or payload.get("payment_method")
        dedup = lowered.get("webhook-id") or f"{event_type}:{object_id}:{vendor_status}"
        return WebhookEvent(
            dedup_key=str(dedup)[:200],
            event_type=event_type,
            object_id=object_id,
            reference_id=payload.get("external_id"),
            status=mapped,
            paid_at=payload.get("paid_at"),
            payment_channel_label=str(channel)[:60] if channel else None,
        )

    data = payload.get("data") or {}
    event_name = str(event_name)
    vendor_status = str(data.get("status") or "").upper()
    if event_name.startswith("payment_method."):
        object_id = data.get("id")
        status = normalize_pm_status(vendor_status)
        suffix = event_name.split(".", 1)[1]
        event_type = (
            f"payment_method.{suffix}"
            if suffix in ("activated", "expired", "failed")
            else "unknown"
        )
        display = extract_display(data)
        failure = data.get("failure_code")
    elif event_name.startswith("payment."):
        # Charge kita = Payment Request; webhook `payment.*` membawa
        # `payment_request_id` (TODO verifikasi Xendit) -- fallback `id`.
        object_id = data.get("payment_request_id") or data.get("id")
        status = normalize_charge_status(vendor_status or event_name.split(".", 1)[1])
        suffix = event_name.split(".", 1)[1]
        event_type = (
            f"payment.{suffix}" if suffix in ("succeeded", "failed", "pending") else "unknown"
        )
        display = PaymentMethodDisplay()
        failure = data.get("failure_code")
    else:
        object_id = data.get("id")
        status = vendor_status.lower() or "unknown"
        event_type = "unknown"
        display = PaymentMethodDisplay()
        failure = None
    dedup = lowered.get("webhook-id") or f"{event_name}:{object_id}:{vendor_status}"
    return WebhookEvent(
        dedup_key=str(dedup)[:200],
        event_type=event_type,
        object_id=str(object_id) if object_id else None,
        reference_id=data.get("reference_id"),
        status=status,
        paid_at=data.get("updated") or data.get("created"),
        failure_code=str(failure)[:80] if failure else None,
        display=display,
    )


class PaymentAdapter:
    """Antarmuka minimal yang harus dipenuhi setiap penyedia pembayaran."""

    provider_name = "base"

    def create_invoice(
        self,
        *,
        external_id: str,
        amount: float,
        description: str,
        payer_email: str,
    ) -> CheckoutResult:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def get_status(self, provider_invoice_id: str) -> PaymentStatus:
        raise NotImplementedError  # pragma: no cover - hanya kontrak

    def ensure_customer(
        self, *, reference_id: str, email: str | None, name: str
    ) -> CustomerResult:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def create_payment_method(
        self,
        *,
        customer_id: str,
        type: str,
        reference_id: str,
        card_token_id: str | None,
        success_return_url: str,
        failure_return_url: str,
    ) -> PaymentMethodResult:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def get_payment_method(
        self, provider_payment_method_id: str
    ) -> PaymentMethodResult:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def expire_payment_method(
        self, provider_payment_method_id: str
    ) -> None:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def charge_saved_method(
        self,
        *,
        provider_payment_method_id: str,
        customer_id: str | None,
        amount: Decimal,
        reference_id: str,
        idempotency_key: str,
        description: str,
    ) -> ChargeResult:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def get_charge_by_reference(
        self, reference_id: str
    ) -> ChargeResult | None:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def parse_webhook(self, headers: dict[str, str], payload: dict) -> WebhookEvent:
        return parse_xendit_style_webhook(headers, payload)
