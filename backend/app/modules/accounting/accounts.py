"""Chart of accounts (bagian akun) — parameter dipisah dari logika kode.

Kategori menentukan penempatan di laporan keuangan:
- aset, kewajiban, ekuitas → Neraca
- pendapatan, beban → Laba Rugi
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    category: str


ACCOUNTS: dict[str, Account] = {
    acc.code: acc
    for acc in [
        Account("1-1000", "Kas", "aset"),
        Account("1-1100", "Bank", "aset"),
        Account("1-1200", "Piutang Usaha", "aset"),
        Account("1-1300", "PPh 21 Dibayar di Muka", "aset"),
        Account("2-1000", "Utang Usaha", "kewajiban"),
        Account("2-1100", "Utang PPh 21", "kewajiban"),
        Account("2-1200", "Utang BPJS", "kewajiban"),
        Account("3-1000", "Modal Disetor", "ekuitas"),
        Account("3-2000", "Laba Ditahan", "ekuitas"),
        Account("4-1000", "Pendapatan Jasa Management Fee", "pendapatan"),
        Account("4-2000", "Pendapatan Lain-lain", "pendapatan"),
        Account("5-1000", "Beban Gaji & Upah", "beban"),
        Account("5-1100", "Beban Lembur", "beban"),
        Account("5-2000", "Beban PPh 21", "beban"),
        Account("5-3000", "Beban BPJS", "beban"),
        Account("5-9000", "Beban Operasional Lainnya", "beban"),
    ]
}

BALANCE_CATEGORIES = ("aset", "kewajiban", "ekuitas")
INCOME_CATEGORIES = ("pendapatan", "beban")


def get_account(code: str) -> Account | None:
    return ACCOUNTS.get(code)
