"""Adapter Xendit untuk pembayaran langganan/top-up saldo (Fase 28).

Pakai REST API Xendit langsung via `httpx` (tanpa SDK vendor) -- konsisten
dengan konvensi codebase ini (lihat `core/esign/privy.py`): tidak ada
`stripe`/`xendit-python` di `pyproject.toml`, semua integrasi vendor
hand-rolled. Auth Basic dengan API key sebagai username, password kosong
(skema resmi Xendit). Semua kegagalan jaringan dipetakan ke HTTPException 502.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.payment.base import (
    Action,
    ChargeResult,
    CheckoutResult,
    CustomerResult,
    PaymentAdapter,
    PaymentGatewayTimeout,
    PaymentMethodResult,
    PaymentStatus,
    extract_display,
    normalize_charge_status,
    normalize_pm_status,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
# Charge bisa dipanggil sinkron dari jalur reaktif auto-reload -- timeout
# pendek; timeout = status `unknown`, direkonsiliasi, bukan dicoba key baru.
_CHARGE_TIMEOUT = httpx.Timeout(20.0, connect=5.0)
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
    provider_name = "xendit"

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

    # ------------------------------------------------------------------
    # Fase 28 lanjutan: metode bayar tersimpan & charge merchant-initiated.
    #
    # SELURUH bagian ini ditulis berdasarkan dokumentasi publik Xendit dan
    # BELUM diverifikasi terhadap akun Aeos (lihat
    # docs/03-architecture/billing-opsi-g-completion.md §5.2). Setiap titik
    # yang bergantung asumsi diberi "TODO verifikasi Xendit". Test TIDAK
    # memanggil kelas ini -- semua test memakai SandboxPaymentAdapter.
    #
    # Aturan keras: payload request pembuatan payment method TIDAK PERNAH
    # di-log (hanya ID & status), dan tidak pernah berisi PAN/CVV -- kartu
    # ditokenisasi di browser lewat Xendit.js, backend hanya menerima token.
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        what: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        try:
            resp = httpx.request(
                method,
                f"{_BASE_URL}{path}",
                auth=self._auth(),
                json=json,
                params=params,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except httpx.HTTPStatusError as exc:
            # Hanya status HTTP, BUKAN body request (bisa berisi token).
            logger.error("Xendit %s HTTP %s", what, exc.response.status_code)
            raise HTTPException(status_code=502, detail=f"Xendit menolak {what}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Xendit %s gagal: %s", what, type(exc).__name__)
            raise HTTPException(status_code=502, detail="Gagal menghubungi Xendit") from exc

    def ensure_customer(self, *, reference_id: str, email: str | None, name: str) -> CustomerResult:
        # TODO verifikasi Xendit: endpoint `POST /customers` (perlu header
        # `API-VERSION`?), field `type=BUSINESS` + `business_detail`, dan
        # pencarian `GET /customers?reference_id=` untuk idempotensi.
        existing = self._request(
            "GET", "/customers", what="pencarian customer", params={"reference_id": reference_id}
        )
        rows = existing.get("data") if isinstance(existing, dict) else None
        if rows:
            return CustomerResult(provider_customer_id=str(rows[0]["id"]))
        payload: dict = {
            "reference_id": reference_id,
            "type": "BUSINESS",
            "business_detail": {"business_name": name[:255]},
        }
        if email:
            payload["email"] = email
        data = self._request("POST", "/customers", what="pembuatan customer", json=payload)
        return CustomerResult(provider_customer_id=str(data["id"]))

    def _pm_result(self, data: dict) -> PaymentMethodResult:
        actions = [
            Action(kind=str(a.get("action") or "redirect").lower(), url=str(a["url"]))
            for a in (data.get("actions") or [])
            if a.get("url")
        ]
        failure = data.get("failure_code")
        return PaymentMethodResult(
            provider_payment_method_id=str(data.get("id") or ""),
            status=normalize_pm_status(data.get("status")),
            actions=actions,
            display=extract_display(data),
            failure_reason=str(failure)[:200] if failure else None,
        )

    def create_payment_method(
        self,
        *,
        customer_id: str,
        type: str,
        reference_id: str,
        card_token_id: str | None,
        success_return_url: str,
        failure_return_url: str,
    ) -> PaymentMethodResult:
        # TODO verifikasi Xendit: Payment Methods API v2 (`/v2/payment_methods`)
        # vs Payments API v3 (`/v3/payment_tokens`) untuk merchant baru; bentuk
        # persis field kartu ber-token (`card.card_information.token_id`?); dan
        # apakah 3DS terjadi di sini atau saat pembuatan token Xendit.js.
        channel_properties = {
            "success_return_url": success_return_url,
            "failure_return_url": failure_return_url,
        }
        payload: dict = {
            "reusability": "MULTIPLE_USE",
            "customer_id": customer_id,
            "reference_id": reference_id,
        }
        if type == "card":
            if not card_token_id:
                raise HTTPException(status_code=422, detail="card_token_id wajib untuk kartu")
            payload["type"] = "CARD"
            payload["card"] = {
                "channel_properties": channel_properties,
                "card_information": {"token_id": card_token_id},
            }
        elif type == "gopay":
            payload["type"] = "EWALLET"
            payload["ewallet"] = {"channel_code": "GOPAY", "channel_properties": channel_properties}
        else:
            raise HTTPException(status_code=422, detail="Tipe metode bayar tidak didukung")
        data = self._request(
            "POST", "/v2/payment_methods", what="pembuatan metode bayar", json=payload
        )
        result = self._pm_result(data)
        logger.info(
            "Xendit payment method %s status=%s", result.provider_payment_method_id, result.status
        )
        return result

    def get_payment_method(self, provider_payment_method_id: str) -> PaymentMethodResult:
        data = self._request(
            "GET", f"/v2/payment_methods/{provider_payment_method_id}", what="status metode bayar"
        )
        return self._pm_result(data)

    def expire_payment_method(self, provider_payment_method_id: str) -> None:
        # TODO verifikasi Xendit: `POST /v2/payment_methods/{id}/expire`.
        self._request(
            "POST",
            f"/v2/payment_methods/{provider_payment_method_id}/expire",
            what="penghapusan metode bayar",
        )

    @staticmethod
    def _charge_result(data: dict) -> ChargeResult:
        failure = data.get("failure_code")
        return ChargeResult(
            provider_charge_id=str(data["id"]) if data.get("id") else None,
            status=normalize_charge_status(data.get("status")),
            failure_code=str(failure)[:80] if failure else None,
            paid_at=data.get("updated"),
        )

    def charge_saved_method(
        self,
        *,
        provider_payment_method_id: str,
        customer_id: str | None,
        amount: Decimal,
        reference_id: str,
        idempotency_key: str,
        description: str,
    ) -> ChargeResult:
        # TODO verifikasi Xendit: (i) charge kartu tersimpan sebagai MIT tanpa
        # 3DS ulang; (ii) GoPay linked account boleh didebit tanpa interaksi
        # pengguna untuk nominal ini (limit GoPay tokenized); (iii) header
        # `idempotency-key` dihormati di `POST /payment_requests`.
        payload: dict = {
            "amount": int(amount),
            "currency": "IDR",
            "payment_method_id": provider_payment_method_id,
            "reference_id": reference_id,
            "description": description[:255],
        }
        if customer_id:
            payload["customer_id"] = customer_id
        try:
            resp = httpx.post(
                f"{_BASE_URL}/payment_requests",
                auth=self._auth(),
                json=payload,
                headers={"idempotency-key": idempotency_key},
                timeout=_CHARGE_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            # Timeout/putus koneksi: tidak bisa dipastikan request tidak
            # sampai -> unknown, direkonsiliasi dengan key yang sama.
            raise PaymentGatewayTimeout(type(exc).__name__) from exc
        if resp.status_code >= 500:
            raise PaymentGatewayTimeout(f"HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise PaymentGatewayTimeout("respons bukan JSON") from exc
        if resp.status_code >= 400:
            code = str(data.get("error_code") or f"HTTP_{resp.status_code}")[:80]
            logger.warning("Xendit charge %s ditolak: %s", reference_id, code)
            return ChargeResult(
                provider_charge_id=None,
                status="failed",
                failure_code=code,
                failure_message=str(data.get("message") or "")[:300] or None,
            )
        return self._charge_result(data)

    def get_charge_by_reference(self, reference_id: str) -> ChargeResult | None:
        # TODO verifikasi Xendit: `GET /payment_requests?reference_id=` dan
        # bentuk respons list (`data: [...]`).
        try:
            resp = httpx.get(
                f"{_BASE_URL}/payment_requests",
                auth=self._auth(),
                params={"reference_id": reference_id},
                timeout=_CHARGE_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentGatewayTimeout(type(exc).__name__) from exc
        rows = data.get("data") if isinstance(data, dict) else data
        if not rows:
            return None
        return self._charge_result(rows[0])
