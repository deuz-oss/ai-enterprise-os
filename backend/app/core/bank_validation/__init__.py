"""Factory adapter validasi rekening bank. Mirror persis pola
`modules/billing/payment_service.py::get_adapter()`.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.core.bank_validation.api_co_id import ApiCoIdAdapter
from app.core.bank_validation.base import BankAccountValidation, BankOption, BankValidationAdapter
from app.core.bank_validation.sandbox import SandboxBankValidationAdapter
from app.core.config import get_settings

__all__ = [
    "BankAccountValidation",
    "BankOption",
    "BankValidationAdapter",
    "get_adapter",
]


def get_adapter() -> BankValidationAdapter:
    settings = get_settings()
    if settings.bank_validation_provider == "sandbox":
        return SandboxBankValidationAdapter()
    if settings.bank_validation_provider == "api_co_id":
        return ApiCoIdAdapter()
    raise HTTPException(
        status_code=503,
        detail=(
            "Integrasi validasi rekening belum aktif. "
            "Set BANK_VALIDATION_PROVIDER (sandbox/api_co_id) di .env."
        ),
    )
