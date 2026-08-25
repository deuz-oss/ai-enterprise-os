"""Perhitungan PPh 21 bulanan.

Parameter tarif dipisah dari logika kode sesuai prinsip roadmap:
semua angka regulasi hidup di konstanta tabel di bawah dan bisa diganti
tanpa menyentuh fungsi perhitungan.

Dua metode yang didukung (PMK 168/2023):
- **TER** (Tarif Efektif Rata-rata): metode default untuk pegawai tetap,
  berdasarkan penghasilan bruto bulanan dan kategori TER (A/B/C) dari
  status PTKP.
- **Pasal 17**: progresif atas PKP setahun (dipakai pegawai tidak tetap /
  hitung mundur); implementasi ini memakai PKP = bruto tahunan - PTKP.

CATATAN VERIFIKASI: angka PTKP & bracket Pasal 17 stabil; tabel TER
perlu dicek ulang terhadap PMK 168/2023 saat pemakaian produksi.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

# ---------- Parameter regulasi (fallback jika DB kosong) ----------

PTKP_DIRI_SENDIRI = 54_000_000
PTKP_KAWIN = 4_500_000
PTKP_TANGGUNGAN = 4_500_000
MAX_TANGGUNGAN = 3

# Pasal 17: lapisan (batas atas PKP setahun, tarif).
PASAL_17_BRACKETS: list[tuple[float, float]] = [
    (60_000_000, 0.05),
    (250_000_000, 0.15),
    (500_000_000, 0.25),
    (5_000_000_000, 0.30),
    (float("inf"), 0.35),
]

# Kategori TER menurut status PTKP.
TER_CATEGORY_A = {"tk_0", "tk_1", "k_0"}
TER_CATEGORY_B = {"tk_2", "tk_3", "k_1", "k_2"}
TER_CATEGORY_C = {"k_3"}

# Tabel TER per kategori: daftar (batas atas bruto bulanan, tarif).
TER_A: list[tuple[float, float]] = [
    (5_400_000, 0.0),
    (5_650_000, 0.0025),
    (5_950_000, 0.005),
    (6_300_000, 0.0075),
    (6_750_000, 0.01),
    (7_500_000, 0.0125),
    (8_550_000, 0.015),
    (9_650_000, 0.0175),
    (10_750_000, 0.02),
    (12_050_000, 0.0225),
    (13_700_000, 0.025),
    (15_550_000, 0.03),
    (17_850_000, 0.035),
    (20_450_000, 0.04),
    (23_600_000, 0.05),
    (27_700_000, 0.06),
    (33_000_000, 0.07),
    (39_300_000, 0.08),
    (47_200_000, 0.09),
    (57_900_000, 0.10),
    (74_500_000, 0.11),
    (104_000_000, 0.12),
    (178_000_000, 0.14),
    (350_000_000, 0.16),
    (500_000_000, 0.18),
    (float("inf"), 0.20),
]

TER_B: list[tuple[float, float]] = [
    (6_200_000, 0.0),
    (6_500_000, 0.0025),
    (6_850_000, 0.005),
    (7_300_000, 0.0075),
    (9_200_000, 0.01),
    (10_750_000, 0.015),
    (11_250_000, 0.02),
    (11_600_000, 0.0225),
    (12_600_000, 0.025),
    (13_600_000, 0.03),
    (14_950_000, 0.035),
    (17_300_000, 0.04),
    (19_200_000, 0.05),
    (21_750_000, 0.06),
    (25_450_000, 0.07),
    (29_850_000, 0.08),
    (35_400_000, 0.09),
    (43_000_000, 0.10),
    (55_500_000, 0.11),
    (73_500_000, 0.12),
    (103_500_000, 0.14),
    (177_500_000, 0.16),
    (349_500_000, 0.18),
    (499_500_000, 0.19),
    (float("inf"), 0.20),
]

TER_C: list[tuple[float, float]] = [
    (6_600_000, 0.0),
    (6_950_000, 0.0025),
    (7_350_000, 0.005),
    (7_800_000, 0.0075),
    (8_850_000, 0.01),
    (9_800_000, 0.0125),
    (10_950_000, 0.015),
    (11_200_000, 0.02),
    (12_050_000, 0.0225),
    (13_250_000, 0.025),
    (15_150_000, 0.03),
    (17_650_000, 0.035),
    (19_750_000, 0.04),
    (23_300_000, 0.05),
    (27_900_000, 0.06),
    (33_800_000, 0.07),
    (41_100_000, 0.08),
    (50_400_000, 0.09),
    (64_700_000, 0.10),
    (85_500_000, 0.11),
    (122_500_000, 0.12),
    (198_500_000, 0.14),
    (402_500_000, 0.16),
    (499_500_000, 0.18),
    (float("inf"), 0.19),
]


def _deser_brackets(raw: Any) -> list[tuple[float, float]]:
    """Deserialisasi JSON brackets: [upper|null, rate] -> [(upper|inf, rate)]."""
    result: list[tuple[float, float]] = []
    for upper, rate in raw:
        result.append((float("inf") if upper is None else float(upper), float(rate)))
    return result


def _get_pph21_config(db, effective_date: date | None):
    if db is None or effective_date is None:
        return None
    try:
        from sqlalchemy import select

        from app.modules.rates.models import Pph21Config

        return (
            db.execute(
                select(Pph21Config)
                .where(Pph21Config.effective_from <= effective_date)
                .order_by(Pph21Config.effective_from.desc())  # noqa: E501
            )
            .scalars()
            .first()
        )
    except Exception:
        return None


@dataclass(frozen=True)
class TaxProfile:
    """Status PTKP karyawan, mis. `k_2` = kawin, 2 tanggungan."""

    marital_status: str  # "tk" atau "k"
    dependents: int = 0
    _config: Any | None = None  # Pph21Config DB row atau None (fallback konstanta)

    @property
    def ptkp_key(self) -> str:
        max_dep = int(self._config.max_tanggungan) if self._config else MAX_TANGGUNGAN
        deps = min(max(self.dependents, 0), max_dep)
        return f"{self.marital_status}_{deps}"

    @property
    def ptkp_annual(self) -> float:
        if self._config:
            base = float(self._config.ptkp_diri)
            if self.marital_status == "k":
                base += float(self._config.ptkp_kawin)
            deps = min(max(self.dependents, 0), int(self._config.max_tanggungan))
            return base + deps * float(self._config.ptkp_tanggungan)
        base = PTKP_DIRI_SENDIRI
        if self.marital_status == "k":
            base += PTKP_KAWIN
        deps = min(max(self.dependents, 0), MAX_TANGGUNGAN)
        return base + deps * PTKP_TANGGUNGAN

    @property
    def ter_table(self) -> list[tuple[float, float]]:
        if self._config:
            key = self.ptkp_key
            # kategori masih hardcoded, tapi tabel dari DB
            if key in TER_CATEGORY_A:
                return _deser_brackets(self._config.ter_a)
            if key in TER_CATEGORY_B:
                return _deser_brackets(self._config.ter_b)
            return _deser_brackets(self._config.ter_c)
        key = self.ptkp_key
        if key in TER_CATEGORY_A:
            return TER_A
        if key in TER_CATEGORY_B:
            return TER_B
        return TER_C

    @property
    def pasal17_brackets(self) -> list[tuple[float, float]]:
        if self._config:
            return _deser_brackets(self._config.pasal17_brackets)
        return PASAL_17_BRACKETS

    @classmethod
    def from_db(
        cls, db, effective_date: date | None, marital_status: str, dependents: int = 0
    ) -> "TaxProfile":
        cfg = _get_pph21_config(db, effective_date)
        return cls(marital_status=marital_status, dependents=dependents, _config=cfg)


def ter_category(profile: TaxProfile) -> str:
    key = profile.ptkp_key
    if key in TER_CATEGORY_A:
        return "A"
    if key in TER_CATEGORY_B:
        return "B"
    return "C"


def compute_ter(gross_monthly: float, profile: TaxProfile) -> float:
    """PPh 21 bulanan metode TER atas penghasilan bruto."""
    for upper_bound, rate in profile.ter_table:
        if gross_monthly <= upper_bound:
            tax = gross_monthly * rate
            return round(tax)
    return 0.0


def compute_pasal17_annual(annual_gross: float, profile: TaxProfile) -> float:
    """PPh 21 setahun metode pasal 17 progresif atas PKP."""
    taxable = max(annual_gross - profile.ptkp_annual, 0)
    tax = 0.0
    previous_bound = 0.0
    for upper_bound, rate in profile.pasal17_brackets:
        layer = min(taxable, upper_bound) - previous_bound
        if layer > 0:
            tax += layer * rate
        previous_bound = upper_bound
        if taxable <= upper_bound:
            break
    return round(tax)


def compute_pasal17_monthly_average(
    monthly_gross: float, months: int, profile: TaxProfile
) -> float:
    """Prorata rata-rata bulanan dari hitungan pasal 17 setahun."""
    if months <= 0:
        return 0.0
    annual_tax = compute_pasal17_annual(monthly_gross * months, profile)
    return round(annual_tax / months)
