"""Aritmetika uang: Decimal + pembulatan eksplisit ke rupiah penuh.

Kolom uang di DB bertipe `Numeric(14, 2)`, tapi perhitungan payroll dulu
memakai `float` + `round()` bawaan Python. Dua masalahnya:

- `float` biner tidak bisa menyimpan tarif seperti 0,0225 secara persis,
  jadi hasil kali bisa jatuh tepat di bawah/atas ,5 dan berbalik arah
  pembulatannya.
- `round()` Python memakai *banker's rounding* (setengah ke genap):
  `round(2.5) == 2`, `round(3.5) == 4` -- bukan pembulatan setengah ke atas
  yang lazim dipakai untuk nominal rupiah di slip/bukti potong.

Semua hitungan uang baru wajib lewat helper di sini. Konversi ke `float`
hanya di batas keluar (JSON response/audit), dan untuk rupiah penuh itu
eksak (bilangan bulat < 2**53).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ZERO = Decimal(0)
_RUPIAH = Decimal(1)


def to_decimal(value: Any) -> Decimal:
    """Konversi aman ke Decimal. `float` lewat `str()` supaya 0.0225 menjadi
    Decimal('0.0225'), bukan ekspansi biner 0.02249999999999999916..."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        if value == float("inf"):
            return Decimal("Infinity")
        return Decimal(str(value))
    return Decimal(value)


def round_rupiah(value: Any) -> Decimal:
    """Bulatkan ke rupiah penuh, setengah ke atas (bukan setengah ke genap)."""
    return to_decimal(value).quantize(_RUPIAH, rounding=ROUND_HALF_UP)


def rupiah_int(value: Any) -> int:
    return int(round_rupiah(value))
