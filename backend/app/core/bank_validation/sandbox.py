"""Adapter sandbox: simulasi validasi rekening bank tanpa vendor eksternal.

Dipakai untuk dev/demo/test, sama pola dgn `core/payment/sandbox.py`.
Aturan deterministik (bukan acak) supaya tes bisa memilih input yang
sengaja lolos/gagal:

- `validate_account`: rekening dianggap VALID kalau `account_number` TIDAK
  diakhiri "0". Nomor yang diakhiri "0" sengaja dianggap tidak
  ditemukan/tidak aktif, supaya kasus gagal juga bisa diuji tanpa mock.
"""

from __future__ import annotations

from app.core.bank_validation.base import BankAccountValidation, BankOption, BankValidationAdapter

_FIXTURE_BANKS = (
    BankOption(code="bank_bri", name="Bank Rakyat Indonesia"),
    BankOption(code="bank_bca", name="Bank Central Asia"),
    BankOption(code="bank_mandiri", name="Bank Mandiri"),
    BankOption(code="bank_bni", name="Bank Negara Indonesia"),
    BankOption(code="bank_cimb", name="CIMB Niaga"),
)


class SandboxBankValidationAdapter(BankValidationAdapter):
    def list_banks(self) -> list[BankOption]:
        return list(_FIXTURE_BANKS)

    def validate_account(
        self, *, bank_code: str, account_number: str, account_name: str
    ) -> BankAccountValidation:
        is_valid = not account_number.endswith("0")
        return BankAccountValidation(
            is_valid=is_valid,
            masked_name="San**** Box****" if is_valid else None,
            raw_message="Rekening ditemukan (sandbox)"
            if is_valid
            else "Rekening tidak ditemukan (sandbox)",
        )
