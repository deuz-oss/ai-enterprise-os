"""Adapter sandbox: simulasi gateway pembayaran tanpa vendor eksternal.

Dipakai untuk dev/demo/test. ID invoice memakai prefiks "sbx-pay-" dan
"dibayar" lewat penyelesaian lokal (endpoint simulate di modul billing),
sama pola dengan `core/esign/sandbox.py::SandboxAdapter`.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.payment.base import CheckoutResult, PaymentAdapter, PaymentStatus


class SandboxPaymentAdapter(PaymentAdapter):
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
