"""Kontrak antarmuka adapter tanda tangan elektronik.

Semua provider (PrivyID, sandbox, dsb.) mengembalikan struktur yang sama
sehingga modul esign tidak perlu tahu detail vendor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SendResult:
    """Hasil pengiriman dokumen ke penyedia TTE."""

    provider_document_id: str
    sign_url: str | None  # link untuk penandatangan (bila disediakan vendor)


@dataclass(frozen=True)
class ProviderStatus:
    """Status dokumen dari sudut pandang penyedia."""

    status: str  # pending | viewed | completed | declined | expired
    signed_at: str | None = None
    raw: dict | None = None


class EsignAdapter:
    """Antarmuka minimal yang harus dipenuhi setiap penyedia TTE."""

    def send_document(
        self,
        *,
        pdf_bytes: bytes,
        file_name: str,
        title: str,
        signer_name: str,
        signer_email: str,
    ) -> SendResult:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def get_status(self, provider_document_id: str) -> ProviderStatus:
        raise NotImplementedError  # pragma: no cover - hanya kontrak
