"""Kontrak antarmuka adapter gateway pembayaran (Fase 28, Opsi G).

Mirror persis pola `core/esign/base.py`: semua provider (Xendit, sandbox)
mengembalikan struktur yang sama sehingga modul billing tidak perlu tahu
detail vendor.
"""

from __future__ import annotations

from dataclasses import dataclass


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


class PaymentAdapter:
    """Antarmuka minimal yang harus dipenuhi setiap penyedia pembayaran."""

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
