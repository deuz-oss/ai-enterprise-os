"""Adapter Xendit untuk pembayaran langganan/top-up saldo (Fase 28).

Pakai REST API Xendit langsung via `httpx` (tanpa SDK vendor) -- konsisten
dengan konvensi codebase ini (lihat `core/esign/privy.py`): tidak ada
`stripe`/`xendit-python` di `pyproject.toml`, semua integrasi vendor
hand-rolled. Auth Basic dengan API key sebagai username, password kosong
(skema resmi Xendit). Semua kegagalan jaringan dipetakan ke HTTPException 502.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.payment.base import CheckoutResult, PaymentAdapter, PaymentStatus

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_BASE_URL = "https://api.xendit.co"

# Pemetaan status invoice Xendit -> status internal.
_STATUS_MAP = {
    "PENDING": "pending",
    "PAID": "paid",
    "SETTLED": "paid",
    "EXPIRED": "expired",
    "FAILED": "failed",
}


class XenditAdapter(PaymentAdapter):
    def _auth(self) -> tuple[str, str]:
        settings = get_settings()
        if not settings.xendit_api_key:
            raise HTTPException(
                status_code=503,
                detail="Kredensial Xendit belum lengkap (XENDIT_API_KEY)",
            )
        return (settings.xendit_api_key, "")

    def create_invoice(
        self,
        *,
        external_id: str,
        amount: float,
        description: str,
        payer_email: str,
    ) -> CheckoutResult:
        payload = {
            "external_id": external_id,
            "amount": amount,
            "description": description,
            "payer_email": payer_email,
            "currency": "IDR",
        }
        try:
            resp = httpx.post(
                f"{_BASE_URL}/v2/invoices",
                auth=self._auth(),
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Xendit create invoice HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
            raise HTTPException(
                status_code=502, detail="Xendit menolak permintaan invoice"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Xendit create invoice gagal: %s", exc)
            raise HTTPException(status_code=502, detail="Gagal menghubungi Xendit") from exc

        invoice_id = str(data.get("id") or "").strip()
        if not invoice_id:
            logger.error("Xendit respon tak dikenal: %s", str(data)[:300])
            raise HTTPException(status_code=502, detail="Respon Xendit tidak dikenali")
        checkout_url = data.get("invoice_url")
        return CheckoutResult(
            provider_invoice_id=invoice_id,
            checkout_url=str(checkout_url) if checkout_url else None,
        )

    def get_status(self, provider_invoice_id: str) -> PaymentStatus:
        try:
            resp = httpx.get(
                f"{_BASE_URL}/v2/invoices/{provider_invoice_id}",
                auth=self._auth(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Xendit status gagal: %s", exc)
            raise HTTPException(status_code=502, detail="Gagal membaca status dari Xendit") from exc

        vendor_status = str(data.get("status") or "PENDING").upper()
        mapped = _STATUS_MAP.get(vendor_status, "pending")
        return PaymentStatus(
            status=mapped,
            paid_at=data.get("paid_at"),
            raw=data,
        )
