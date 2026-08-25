"""Template bagan akun default untuk jasa outsourcing (PRD §8.1).

Dipakai migrasi (seed tenant lama) dan bootstrap/provisioning (tenant baru).
"""

from __future__ import annotations

# (code, name, group_type, normal_balance, is_cash_bank, is_control_ar_ap)
DEFAULT_COA: list[tuple[str, str, str, str, bool, bool]] = [
    ("1-1000", "Kas", "aset_lancar", "debit", True, False),
    ("1-1100", "Bank", "aset_lancar", "debit", True, False),
    ("1-1200", "Piutang Usaha", "aset_lancar", "debit", False, True),
    ("1-1300", "PPh 21 Dibayar di Muka", "aset_lancar", "debit", False, False),
    ("1-1400", "PPN Masukan", "aset_lancar", "debit", False, False),
    ("1-2000", "Aset Tetap — Peralatan Kantor", "aset_tetap", "debit", False, False),
    ("1-2100", "Akumulasi Penyusutan Peralatan", "aset_tetap", "kredit", False, False),
    ("2-1000", "Utang Usaha", "liabilitas_pendek", "kredit", False, True),
    ("2-1100", "Utang PPh 21", "liabilitas_pendek", "kredit", False, False),
    ("2-1200", "Utang BPJS", "liabilitas_pendek", "kredit", False, False),
    ("2-1300", "Utang PPN Keluaran", "liabilitas_pendek", "kredit", False, False),
    ("3-1000", "Modal Disetor", "ekuitas", "kredit", False, False),
    ("3-2000", "Laba Ditahan", "ekuitas", "kredit", False, False),
    ("3-3000", "Laba Tahun Berjalan", "ekuitas", "kredit", False, False),
    ("4-1000", "Pendapatan Jasa Management Fee", "pendapatan", "kredit", False, False),
    ("4-2000", "Pendapatan Operasional Tenaga Kerja", "pendapatan", "kredit", False, False),
    ("4-9000", "Pendapatan Lain-lain", "pendapatan_lain", "kredit", False, False),
    ("5-1000", "Beban Gaji & Upah", "beban_usaha", "debit", False, False),
    ("5-1100", "Beban Lembur", "beban_usaha", "debit", False, False),
    ("5-2000", "Beban PPh 21", "beban_usaha", "debit", False, False),
    ("5-3000", "Beban BPJS", "beban_usaha", "debit", False, False),
    ("5-4000", "Beban Rekrutmen & Penempatan", "beban_usaha", "debit", False, False),
    ("5-5000", "HPP Tenaga Kerja Proyek", "hpp", "debit", False, False),
    ("5-9000", "Beban Operasional Lainnya", "beban_usaha", "debit", False, False),
    ("5-6000", "Beban Penyusutan Aset Tetap", "beban_usaha", "debit", False, False),
    ("6-1000", "Beban Bunga Bank", "beban_lain", "debit", False, False),
]

# Event auto-journal → pasangan akun default (debit, kredit).
# Event multi-baris (payroll/invoice) membangun lines sendiri di hook;
# rule hanya menentukan aktif/tidaknya event.
DEFAULT_RULES: list[tuple[str, str, str]] = [
    ("invoice_issued", "1-1200", "4-1000"),
    ("invoice_paid", "1-1100", "1-1200"),
    ("payroll_finalized_internal", "5-1000", "2-1000"),
    ("payroll_finalized_proyek", "5-5000", "2-1000"),
    ("pr_executed", "2-1000", "1-1100"),
    ("opening_balance", "1-1000", "3-1000"),
    # Modul kas & bank / pembelian / aset tetap
    ("cash_receipt", "1-1100", "4-1000"),
    ("cash_payment", "5-9000", "1-1100"),
    ("bank_transfer", "1-1100", "1-1000"),
    ("purchase_received", "5-9000", "2-1000"),
    ("purchase_paid", "2-1000", "1-1100"),
    ("asset_acquired", "1-2000", "1-1100"),
    ("depreciation_monthly", "5-6000", "1-2100"),
    ("asset_disposed", "1-1100", "1-2000"),
]
