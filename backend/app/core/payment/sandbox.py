"""Adapter sandbox: simulasi gateway pembayaran tanpa vendor eksternal.

Dipakai untuk dev/demo/test. ID invoice memakai prefiks "sbx-pay-" dan
"dibayar" lewat penyelesaian lokal (endpoint `/billing/sandbox/...` di modul
billing), sama pola dengan `core/esign/sandbox.py::SandboxAdapter`.

Metode bayar & charge (Fase 28 lanjutan) deterministik lewat "token ajaib":

| card_token_id        | hasil pembuatan PM / charge                       |
|----------------------|---------------------------------------------------|
| sbx-tok-ok (default) | PM aktif (VISA 4242, 12/2030); charge sukses      |
| sbx-tok-3ds          | PM requires_action (redirect otorisasi sandbox)   |
| sbx-tok-fail         | PM gagal                                          |
| sbx-tok-decline      | PM aktif; charge gagal CARD_DECLINED              |
| sbx-tok-pending      | PM aktif; charge pending (selesai via simulasi)   |
| sbx-tok-timeout      | PM aktif; charge timeout SETELAH tercatat di      |
|                      | "gateway" (menguji rekonsiliasi status unknown)   |

Perilaku di-encode ke ID payment method (`sbx-pm-<perilaku>-<hex>`) supaya
stateless lintas restart. Charge per idempotency key disimpan di dict
modul-level: kirim ulang dengan key yang sama mengembalikan hasil yang sama
(tidak ada charge ganda), persis kontrak idempotensi gateway sungguhan.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.core.payment.base import (
    Action,
    ChargeResult,
    CheckoutResult,
    CustomerResult,
    PaymentAdapter,
    PaymentGatewayTimeout,
    PaymentMethodDisplay,
    PaymentMethodResult,
    PaymentStatus,
)

_BEHAVIOURS = {"ok", "3ds", "fail", "decline", "pending", "timeout"}

# reference_id/idempotency_key -> ChargeResult (state "gateway" sandbox).
_CHARGES: dict[str, ChargeResult] = {}
# Penghitung panggilan charge_saved_method (dipakai test anti-charge-ganda).
CHARGE_CALLS: list[str] = []


def _behaviour_from_token(token: str | None) -> str:
    if token and token.startswith("sbx-tok-"):
        kind = token[len("sbx-tok-") :]
        if kind in _BEHAVIOURS:
            return kind
    return "ok"


def _behaviour_from_pm(pm_id: str) -> str:
    parts = pm_id.split("-")
    if len(parts) >= 4 and parts[0] == "sbx" and parts[1] == "pm" and parts[2] in _BEHAVIOURS:
        return parts[2]
    return "ok"


def sandbox_settle_charge(reference_id: str, status: str) -> ChargeResult:
    """Ubah state charge sandbox (dipakai endpoint simulasi webhook)."""
    previous = _CHARGES.get(reference_id)
    result = ChargeResult(
        provider_charge_id=previous.provider_charge_id if previous else f"sbx-pr-{uuid4().hex}",
        status=status,
        failure_code="CARD_DECLINED" if status == "failed" else None,
    )
    _CHARGES[reference_id] = result
    return result


class SandboxPaymentAdapter(PaymentAdapter):
    provider_name = "sandbox"

    def create_invoice(
        self,
        *,
        external_id: str,
        amount: float,
        description: str,
        payer_email: str,
    ) -> CheckoutResult:
        invoice_id = f"sbx-pay-{uuid4().hex[:12]}"
        return CheckoutResult(
            provider_invoice_id=invoice_id,
            checkout_url=f"/sandbox/billing/{invoice_id}/pay",
        )

    def get_status(self, provider_invoice_id: str) -> PaymentStatus:
        # Sandbox tidak punya state server; status sebenarnya ada di DB lokal.
        return PaymentStatus(status="pending", raw={"provider": "sandbox"})

    def ensure_customer(self, *, reference_id: str, email: str | None, name: str) -> CustomerResult:
        return CustomerResult(provider_customer_id=f"sbx-cust-{reference_id[-12:]}")

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
        behaviour = _behaviour_from_token(card_token_id) if type == "card" else "gopay"
        pm_behaviour = behaviour if behaviour in _BEHAVIOURS else "ok"
        pm_id = f"sbx-pm-{pm_behaviour}-{uuid4().hex[:12]}"
        authorize = Action(
            kind="redirect", url=f"/sandbox/billing/payment-methods/{reference_id}/authorize"
        )
        if type == "gopay":
            return PaymentMethodResult(
                provider_payment_method_id=pm_id,
                status="pending_activation",
                actions=[authorize],
            )
        if behaviour == "fail":
            return PaymentMethodResult(
                provider_payment_method_id=pm_id, status="failed", failure_reason="CARD_INVALID"
            )
        display = PaymentMethodDisplay(
            card_brand="VISA", card_last4="4242", card_exp_month=12, card_exp_year=2030
        )
        if behaviour == "3ds":
            return PaymentMethodResult(
                provider_payment_method_id=pm_id,
                status="pending_activation",
                actions=[authorize],
                display=display,
            )
        return PaymentMethodResult(
            provider_payment_method_id=pm_id, status="active", display=display
        )

    def get_payment_method(self, provider_payment_method_id: str) -> PaymentMethodResult:
        return PaymentMethodResult(
            provider_payment_method_id=provider_payment_method_id, status="active"
        )

    def expire_payment_method(self, provider_payment_method_id: str) -> None:
        return None

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
        CHARGE_CALLS.append(idempotency_key)
        if idempotency_key in _CHARGES:
            return _CHARGES[idempotency_key]
        behaviour = _behaviour_from_pm(provider_payment_method_id)
        charge_id = f"sbx-pr-{uuid4().hex}"
        if behaviour == "decline":
            result = ChargeResult(
                provider_charge_id=charge_id,
                status="failed",
                failure_code="CARD_DECLINED",
                failure_message="Kartu ditolak (sandbox)",
            )
        elif behaviour == "pending":
            result = ChargeResult(provider_charge_id=charge_id, status="pending")
        else:
            result = ChargeResult(provider_charge_id=charge_id, status="succeeded")
        _CHARGES[idempotency_key] = result
        if behaviour == "timeout":
            # Charge SUDAH tercatat sukses di "gateway", tapi respons hilang.
            raise PaymentGatewayTimeout("sandbox timeout")
        return result

    def get_charge_by_reference(self, reference_id: str) -> ChargeResult | None:
        return _CHARGES.get(reference_id)
