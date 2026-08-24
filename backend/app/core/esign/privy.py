"""Adapter PrivyID untuk tanda tangan elektronik tersertifikasi BSrE.

Catatan implementasi: skema endpoint mengikuti REST API PrivyID v1 yang
umum dipakai (auth token → uploadDocument). Beberapa nama field dapat
berbeda antar kontrak merchant — sesuaikan bila kredensial produksi
sudah tersedia. Semua kegagalan jaringan dipetakan ke HTTPException 502.
"""

from __future__ import annotations

import base64
import logging
import time
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.esign.base import EsignAdapter, ProviderStatus, SendResult

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_TOKEN_TTL_SECONDS = 600

# Pemetaan status dokumen PrivyID → status internal.
_STATUS_MAP = {
    "inprogress": "pending",
    "pending": "pending",
    "viewed": "viewed",
    "completed": "completed",
    "done": "completed",
    "declined": "declined",
    "cancelled": "declined",
    "expired": "expired",
}


class PrivyAdapter(EsignAdapter):
    def __init__(self) -> None:
        self._token: str | None = None
        self._token_time: float = 0.0

    def _base_headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "X-Requested-With": "XMLHttpRequest",
            "Merchant-Key-Api": settings.privy_merchant_key or "",
        }

    def _access_token(self) -> str:
        """Ambil (dan cache singkat) access token dari /auth/token."""
        now = time.monotonic()
        if self._token and now - self._token_time < _TOKEN_TTL_SECONDS:
            return self._token
        settings = get_settings()
        if not (settings.privy_api_url and settings.privy_username and settings.privy_password):
            raise HTTPException(
                status_code=503,
                detail="Kredensial PrivyID belum lengkap (PRIVY_API_URL/USERNAME/PASSWORD)",
            )
        url = settings.privy_api_url.rstrip("/") + "/auth/token"
        try:
            resp = httpx.post(
                url,
                headers=self._base_headers(),
                auth=(settings.privy_username, settings.privy_password),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            token = resp.json()["access_token"]
        except httpx.HTTPStatusError as exc:
            logger.error(
                "PrivyID auth HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
            )
            raise HTTPException(status_code=502, detail="PrivyID menolak autentikasi") from exc
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            logger.error("PrivyID auth gagal: %s", exc)
            raise HTTPException(status_code=502, detail="Gagal menghubungi PrivyID") from exc
        self._token = str(token)
        self._token_time = now
        return self._token

    def send_document(
        self,
        *,
        pdf_bytes: bytes,
        file_name: str,
        title: str,
        signer_name: str,
        signer_email: str,
    ) -> SendResult:
        settings = get_settings()
        assert settings.privy_api_url  # sudah divalidasi saat ambil token
        payload = {
            "identifier": f"{title}-{uuid4().hex[:8]}",
            "document_type": "Paragraph",
            "file": {
                "base64": base64.b64encode(pdf_bytes).decode("ascii"),
                "filename": file_name,
                "extension": file_name.rsplit(".", 1)[-1].lower() or "pdf",
            },
            "recipients": [
                {"pry_id": signer_email, "type": "Signer", "name": signer_name, "sequence": 0}
            ],
        }
        headers = self._base_headers() | {"Authorization": f"Bearer {self._access_token()}"}
        url = settings.privy_api_url.rstrip("/") + "/uploadDocument"
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json().get("data") or {}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "PrivyID upload HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
            )
            raise HTTPException(status_code=502, detail="PrivyID menolak dokumen") from exc
        except (httpx.HTTPError, AttributeError, ValueError) as exc:
            logger.error("PrivyID upload gagal: %s", exc)
            raise HTTPException(
                status_code=502, detail="Gagal mengirim dokumen ke PrivyID"
            ) from exc

        doc_id = str(data.get("document_token") or data.get("id") or "").strip()
        if not doc_id:
            logger.error("PrivyID respon tak dikenal: %s", str(resp.json())[:300])
            raise HTTPException(status_code=502, detail="Respon PrivyID tidak dikenali")
        sign_url = data.get("url") or data.get("sign_url")
        return SendResult(provider_document_id=doc_id, sign_url=str(sign_url) if sign_url else None)

    def get_status(self, provider_document_id: str) -> ProviderStatus:
        settings = get_settings()
        assert settings.privy_api_url
        headers = self._base_headers() | {"Authorization": f"Bearer {self._access_token()}"}
        url = f"{settings.privy_api_url.rstrip('/')}/documents/{provider_document_id}"
        try:
            resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            raw = resp.json().get("data") or {}
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("PrivyID status gagal: %s", exc)
            raise HTTPException(
                status_code=502, detail="Gagal membaca status dari PrivyID"
            ) from exc
        vendor_status = str(raw.get("status") or "pending").lower()
        mapped = _STATUS_MAP.get(vendor_status, "pending")
        signed_recipient = next(
            (r for r in raw.get("recipients", []) if str(r.get("status", "")).lower() == "done"),
            None,
        )
        return ProviderStatus(
            status=mapped,
            signed_at=(signed_recipient or {}).get("sign_at"),
            raw=raw,
        )
