"""Kontrak antarmuka adapter validasi rekening bank.

Mirror persis pola `core/payment/base.py`: semua provider (api.co.id,
sandbox) mengembalikan struktur yang sama sehingga modul HRD tidak perlu
tahu detail vendor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankOption:
    """Satu bank yang didukung provider, utk populate dropdown pilih bank."""

    code: str  # slug provider, mis. "bank_bri"
    name: str  # label tampilan, mis. "Bank Rakyat Indonesia"


@dataclass(frozen=True)
class BankAccountValidation:
    """Hasil cek satu rekening ke provider.

    `masked_name` SENGAJA sebagian tersamar (kebijakan privasi provider,
    mis. "Rif**** Eln****") -- jangan pernah dipakai utk pencocokan nama
    otomatis/exact-match ke `Employee.full_name`, cuma utk HR eyeball
    manual. `is_valid` (rekening ada & aktif di bank) adalah satu-satunya
    sinyal boolean bersih yang bisa diandalkan dari respons ini.
    """

    is_valid: bool
    masked_name: str | None
    raw_message: str | None


class BankValidationAdapter:
    """Antarmuka minimal yang harus dipenuhi setiap penyedia validasi rekening."""

    def list_banks(self) -> list[BankOption]:  # pragma: no cover - hanya kontrak
        raise NotImplementedError

    def validate_account(
        self, *, bank_code: str, account_number: str, account_name: str
    ) -> BankAccountValidation:  # pragma: no cover - hanya kontrak
        raise NotImplementedError
