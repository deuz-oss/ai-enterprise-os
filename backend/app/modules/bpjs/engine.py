"""Mesin perhitungan iuran BPJS Kesehatan & Ketenagakerjaan.

Mengikuti pola `payroll/tax.py`: seluruh angka regulasi hidup di konstanta
tabel di bawah dan bisa diperbarui tanpa menyentuh fungsi perhitungan.
Fungsi murni (tanpa I/O) agar mudah dites dan dipakai ulang.

Dasar peraturan (per 2025):
- BPJS Kesehatan: total 5% dari gaji (4% perusahaan + 1% karyawan),
  gaji dibatasi maksimum Rp12.000.000 (PMK 76/2016).
- BPJS Ketenagakerjaan (berbasis upah, cap JP berubah tiap tahun):
  - JHT: 3,7% perusahaan + 2% karyawan
  - JP : 2% perusahaan + 1% karyawan, upah di-cap
  - JKK: 0,24%–1,27% sesuai kelas risiko perusahaan (I–V), ditanggung perusahaan
  - JKM: 0,3%, ditanggung perusahaan
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.money import ZERO, rupiah_int, to_decimal

# ---- BPJS Kesehatan ----
KESEHATAN_EMPLOYER = 0.04
KESEHATAN_EMPLOYEE = 0.01
KESEHATAN_SALARY_CAP = 12_000_000

# ---- BPJS Ketenagakerjaan ----
JHT_EMPLOYER = 0.037
JHT_EMPLOYEE = 0.02
JP_EMPLOYER = 0.02
JP_EMPLOYEE = 0.01
JP_SALARY_CAP = 10_547_400  # batas atas upah JP 2025; perbarui tiap tahun regulasi
JKM_RATE = 0.003

# Kelas risiko JKK (aturan Menteri Ketenagakerjaan): kategori → tarif
JKK_RATES: dict[int, float] = {
    1: 0.0024,
    2: 0.0038,
    3: 0.0054,
    4: 0.0089,
    5: 0.0127,
}
# Default pekerja outsourcing umumnya kategori II; override per karyawan.
DEFAULT_JKK_CATEGORY = 2


@dataclass(frozen=True)
class BpjsBreakdown:
    """Rincian iuran seorang karyawan untuk satu bulan."""

    salary_kesehatan: int
    salary_jp: int
    # BPJS Kesehatan
    kes_employer: int
    kes_employee: int
    # BPJS Ketenagakerjaan
    jkk: int
    jkm: int
    jht_employer: int
    jht_employee: int
    jp_employer: int
    jp_employee: int

    @property
    def employer_total(self) -> int:
        return self.kes_employer + self.jkk + self.jkm + self.jht_employer + self.jp_employer

    @property
    def employee_total(self) -> int:
        return self.kes_employee + self.jht_employee + self.jp_employee

    @property
    def grand_total(self) -> int:
        return self.employer_total + self.employee_total


def _jkk_rate(category: int | None, config=None) -> Decimal:
    return to_decimal(_jkk_rate_raw(category, config))


def _jkk_rate_raw(category: int | None, config=None) -> float:
    if config is not None:
        # jkk_rates disimpan sebagai JSON dict str->float
        raw = config.jkk_rates if hasattr(config, "jkk_rates") else JKK_RATES
        # normalisasi key ke int
        table = {
            int(k): float(v)
            for k, v in (raw.items() if isinstance(raw, dict) else JKK_RATES.items())
        }  # noqa: E501
        default_cat = int(getattr(config, "default_jkk_category", DEFAULT_JKK_CATEGORY))
        return table.get(
            category or default_cat, table.get(default_cat, JKK_RATES[DEFAULT_JKK_CATEGORY])
        )  # noqa: E501
    return JKK_RATES.get(category or DEFAULT_JKK_CATEGORY, JKK_RATES[DEFAULT_JKK_CATEGORY])


def _get_bpjs_config(db, effective_date):
    # Tanpa try/except -- lihat catatan di payroll/tax.py::_get_pph21_config.
    if db is None or effective_date is None:
        return None
    from datetime import date as _date

    from sqlalchemy import select

    from app.modules.rates.models import BpjsConfig

    if isinstance(effective_date, str):
        effective_date = _date.fromisoformat(effective_date)
    return (
        db.execute(
            select(BpjsConfig)
            .where(BpjsConfig.effective_from <= effective_date)
            .order_by(BpjsConfig.effective_from.desc())
        )
        .scalars()
        .first()
    )


def compute_contribution(
    base_salary: Any,
    jkk_risk_category: int | None = None,
    _config=None,
    db=None,
    effective_date=None,
) -> BpjsBreakdown:
    """Hitung iuran bulanan dari gaji pokok (dengan batas atas per program).

    Hitungan dalam Decimal, dibulatkan setengah-ke-atas ke rupiah penuh --
    lihat `app/core/money.py` kenapa bukan float + `round()`.
    """
    config = _config or _get_bpjs_config(db, effective_date)
    if config is not None:
        kes_emp = to_decimal(config.kesehatan_employer)
        kes_empl = to_decimal(config.kesehatan_employee)
        kes_cap = to_decimal(config.kesehatan_cap)
        jht_emp = to_decimal(config.jht_employer)
        jht_empl = to_decimal(config.jht_employee)
        jp_emp = to_decimal(config.jp_employer)
        jp_empl = to_decimal(config.jp_employee)
        jp_cap = to_decimal(config.jp_cap)
        jkm = to_decimal(config.jkm_rate)
        jkk_rate = _jkk_rate(jkk_risk_category, config)
    else:
        kes_emp = to_decimal(KESEHATAN_EMPLOYER)
        kes_empl = to_decimal(KESEHATAN_EMPLOYEE)
        kes_cap = to_decimal(KESEHATAN_SALARY_CAP)
        jht_emp = to_decimal(JHT_EMPLOYER)
        jht_empl = to_decimal(JHT_EMPLOYEE)
        jp_emp = to_decimal(JP_EMPLOYER)
        jp_empl = to_decimal(JP_EMPLOYEE)
        jp_cap = to_decimal(JP_SALARY_CAP)
        jkm = to_decimal(JKM_RATE)
        jkk_rate = _jkk_rate(jkk_risk_category)

    salary = max(ZERO, to_decimal(base_salary))
    salary_kes = rupiah_int(min(salary, kes_cap))
    salary_jp = rupiah_int(min(salary, jp_cap))
    salary_tk = rupiah_int(salary)  # JHT/JKK/JKM tanpa batas atas upah

    return BpjsBreakdown(
        salary_kesehatan=salary_kes,
        salary_jp=salary_jp,
        kes_employer=rupiah_int(salary_kes * kes_emp),
        kes_employee=rupiah_int(salary_kes * kes_empl),
        jkk=rupiah_int(salary_tk * jkk_rate),
        jkm=rupiah_int(salary_tk * jkm),
        jht_employer=rupiah_int(salary_tk * jht_emp),
        jht_employee=rupiah_int(salary_tk * jht_empl),
        jp_employer=rupiah_int(salary_jp * jp_emp),
        jp_employee=rupiah_int(salary_jp * jp_empl),
    )
