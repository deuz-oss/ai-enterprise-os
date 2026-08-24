"""Adapter sandbox: simulasi penyedia TTE tanpa vendor eksternal.

Dipakai untuk dev/demo/test. ID dokumen memakai prefiks "sbx-" dan status
dikelola lokal (penyelesaian lewat endpoint simulate di modul esign).
"""

from __future__ import annotations

from uuid import uuid4

from app.core.esign.base import EsignAdapter, ProviderStatus, SendResult


class SandboxAdapter(EsignAdapter):
    def send_document(
        self,
        *,
        pdf_bytes: bytes,
        file_name: str,
        title: str,
        signer_name: str,
        signer_email: str,
    ) -> SendResult:
        doc_id = f"sbx-{uuid4().hex[:12]}"
        return SendResult(
            provider_document_id=doc_id,
            sign_url=f"/sandbox/esign/{doc_id}/sign",
        )

    def get_status(self, provider_document_id: str) -> ProviderStatus:
        # Sandbox tidak punya state server; status sebenarnya ada di DB lokal.
        return ProviderStatus(status="pending", raw={"provider": "sandbox"})
