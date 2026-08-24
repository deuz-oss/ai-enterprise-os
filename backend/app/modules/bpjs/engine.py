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


def _jkk_rate(category: int | None) -> float:
    return JKK_RATES.get(category or DEFAULT_JKK_CATEGORY, JKK_RATES[DEFAULT_JKK_CATEGORY])


def compute_contribution(
    base_salary: float, jkk_risk_category: int | None = None
) -> BpjsBreakdown:
    """Hitung iuran bulanan dari gaji pokok (dengan batas atas per program)."""
    salary = max(0.0, float(base_salary))
    salary_kes = round(min(salary, KESEHATAN_SALARY_CAP))
    salary_jp = round(min(salary, JP_SALARY_CAP))
    salary_tk = round(salary)  # JHT/JKK/JKM tanpa batas atas upah

    jkk_rate = _jkk_rate(jkk_risk_category)
    return BpjsBreakdown(
        salary_kesehatan=salary_kes,
        salary_jp=salary_jp,
        kes_employer=round(salary_kes * KESEHATAN_EMPLOYER),
        kes_employee=round(salary_kes * KESEHATAN_EMPLOYEE),
        jkk=round(salary_tk * jkk_rate),
        jkm=round(salary_tk * JKM_RATE),
        jht_employer=round(salary_tk * JHT_EMPLOYER),
        jht_employee=round(salary_tk * JHT_EMPLOYEE),
        jp_employer=round(salary_jp * JP_EMPLOYER),
        jp_employee=round(salary_jp * JP_EMPLOYEE),
    )
