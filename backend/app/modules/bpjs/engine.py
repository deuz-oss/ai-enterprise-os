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


def _jkk_rate(category: int | None, config=None) -> float:
    if config is not None:
        # jkk_rates disimpan sebagai JSON dict str->float
        raw = config.jkk_rates if hasattr(config, "jkk_rates") else JKK_RATES
        # normalisasi key ke int
        table = {int(k): float(v) for k, v in (raw.items() if isinstance(raw, dict) else JKK_RATES.items())}  # noqa: E501
        default_cat = int(getattr(config, "default_jkk_category", DEFAULT_JKK_CATEGORY))
        return table.get(category or default_cat, table.get(default_cat, JKK_RATES[DEFAULT_JKK_CATEGORY]))  # noqa: E501
    return JKK_RATES.get(category or DEFAULT_JKK_CATEGORY, JKK_RATES[DEFAULT_JKK_CATEGORY])


def _get_bpjs_config(db, effective_date):
    if db is None or effective_date is None:
        return None
    try:
        from datetime import date as _date

        from sqlalchemy import select

        from app.modules.rates.models import BpjsConfig

        if isinstance(effective_date, str):
            effective_date = _date.fromisoformat(effective_date)
        return db.execute(
            select(BpjsConfig).where(BpjsConfig.effective_from <= effective_date).order_by(BpjsConfig.effective_from.desc())  # noqa: E501
        ).scalars().first()
    except Exception:
        return None


def compute_contribution(
    base_salary: float, jkk_risk_category: int | None = None, _config=None, db=None, effective_date=None  # noqa: E501
) -> BpjsBreakdown:
    """Hitung iuran bulanan dari gaji pokok (dengan batas atas per program)."""
    # Resolve config dari DB jika db disediakan
    config = _config or _get_bpjs_config(db, effective_date)
    if config is not None:
        kes_emp = float(config.kesehatan_employer)
        kes_empl = float(config.kesehatan_employee)
        kes_cap = float(config.kesehatan_cap)
        jht_emp = float(config.jht_employer)
        jht_empl = float(config.jht_employee)
        jp_emp = float(config.jp_employer)
        jp_empl = float(config.jp_employee)
        jp_cap = float(config.jp_cap)
        jkm = float(config.jkm_rate)
        jkk_rate_val = _jkk_rate(jkk_risk_category, config)
    else:
        kes_emp = KESEHATAN_EMPLOYER
        kes_empl = KESEHATAN_EMPLOYEE
        kes_cap = KESEHATAN_SALARY_CAP
        jht_emp = JHT_EMPLOYER
        jht_empl = JHT_EMPLOYEE
        jp_emp = JP_EMPLOYER
        jp_empl = JP_EMPLOYEE
        jp_cap = JP_SALARY_CAP
        jkm = JKM_RATE
        jkk_rate_val = _jkk_rate(jkk_risk_category)

    salary = max(0.0, float(base_salary))
    salary_kes = round(min(salary, kes_cap))
    salary_jp = round(min(salary, jp_cap))
    salary_tk = round(salary)  # JHT/JKK/JKM tanpa batas atas upah

    jkk_rate = jkk_rate_val
    return BpjsBreakdown(
        salary_kesehatan=salary_kes,
        salary_jp=salary_jp,
        kes_employer=round(salary_kes * kes_emp),
        kes_employee=round(salary_kes * kes_empl),
        jkk=round(salary_tk * jkk_rate),
        jkm=round(salary_tk * jkm),
        jht_employer=round(salary_tk * jht_emp),
        jht_employee=round(salary_tk * jht_empl),
        jp_employer=round(salary_jp * jp_emp),
        jp_employee=round(salary_jp * jp_empl),
    )
