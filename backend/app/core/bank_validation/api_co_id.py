"""Adapter api.co.id untuk validasi rekening bank Indonesia.

Pakai REST API api.co.id langsung via `httpx` (tanpa SDK vendor) --
konsisten dengan konvensi codebase ini (lihat `core/payment/xendit.py`,
`core/esign/privy.py`): semua integrasi vendor hand-rolled. Auth lewat
header `x-api-co-id`. Semua kegagalan jaringan dipetakan ke HTTPException
502 -- BEDA dari `hrd/service.py::_revalidate_bank_account` yang menelan
exception ini demi best-effort; adapter di sini TETAP raise supaya tetap
reusable/testable independen dari call site.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from fastapi import HTTPException

from app.core.bank_validation.base import BankAccountValidation, BankOption, BankValidationAdapter
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_BASE_URL = "https://api.co.id"


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.bank_validation_api_key:
        raise HTTPException(
            status_code=503,
            detail="Kredensial api.co.id belum lengkap (BANK_VALIDATION_API_KEY)",
        )
    return {"x-api-co-id": settings.bank_validation_api_key}


@lru_cache(maxsize=1)
def _fetch_banks_cached() -> tuple[BankOption, ...]:
    """Daftar bank jarang berubah -- cache seumur proses, tanpa TTL/tabel DB."""
    try:
        resp = httpx.get(
            f"{_BASE_URL}/validation/bank/available",
            headers=_auth_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "api.co.id list bank HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
        )
        raise HTTPException(
            status_code=502, detail="api.co.id menolak permintaan daftar bank"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("api.co.id list bank gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal menghubungi api.co.id") from exc

    banks = data.get("data") or data.get("banks") or []
    return tuple(
        BankOption(
            code=str(b.get("bank_code") or b.get("code") or ""), name=str(b.get("name") or "")
        )
        for b in banks
        if b.get("bank_code") or b.get("code")
    )


class ApiCoIdAdapter(BankValidationAdapter):
    def list_banks(self) -> list[BankOption]:
        return list(_fetch_banks_cached())

    def validate_account(
        self, *, bank_code: str, account_number: str, account_name: str
    ) -> BankAccountValidation:
        payload = {
            "bank_code": bank_code,
            "account_number": account_number,
            "account_name": account_name,
        }
        try:
            resp = httpx.post(
                f"{_BASE_URL}/validation/bank",
                headers={**_auth_headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "api.co.id validate HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
            )
            raise HTTPException(
                status_code=502, detail="api.co.id menolak permintaan validasi rekening"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("api.co.id validate gagal: %s", exc)
            raise HTTPException(status_code=502, detail="Gagal menghubungi api.co.id") from exc

        data = body.get("data") or {}
        return BankAccountValidation(
            is_valid=bool(data.get("is_valid")),
            masked_name=data.get("name"),
            raw_message=data.get("message") or body.get("message"),
        )
