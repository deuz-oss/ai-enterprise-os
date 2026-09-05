"""Registry aplikasi & bundle portofolio (single source of truth PRD v3.0 Final).

PRD v3.0 Final — Opsi F: Talent-Centric Metered:
- Internal mode (app_mode=internal atau tenants.billing_mode=internal): semua bundle aktif.
- Commercial mode (app_mode=commercial + tenants.billing_mode=commercial): lisensi per SKU, metered.
- 6 keys teknis dipertahankan (backward-compat), dijual sebagai 4 paket F:
  Talent Cloud = sales_crm+recruitment, Workforce Cloud = people_ops,
  Revenue Cloud = payroll+finance, Govern = accounting.
  BUNDLE_REGISTRY F adalah paket komersial, APP_REGISTRY adalah SKU teknis.

Prefix yang TIDAK terdaftar (auth, platform, overview, files, health, /apps,
chat, pages, dashboard) adalah FOUNDATION gratis — selalu aktif.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    key: str
    name: str
    emoji: str
    accent: str
    description: str
    depends_on: tuple[str, ...]
    route_prefixes: tuple[str, ...]
    bundle: str
    meter: str  # metered metric untuk Opsi F


# ---- 6 SKU Teknis + 1 Add-on (PRD v3.0) ----
APP_REGISTRY: dict[str, AppSpec] = {
    spec.key: spec
    for spec in (
        AppSpec(
            key="sales_crm",
            name="Sales CRM",
            emoji="🎯",
            accent="blue",
            description=(
                "Pipeline, aktivitas, konversi klien → klien aktif otomatis saat onboarding."
            ),
            depends_on=(),
            route_prefixes=("/leads", "/clients"),
            bundle="talent",
            meter="talent_active",
        ),
        AppSpec(
            key="recruitment",
            name="Recruitment",
            emoji="🧲",
            accent="purple",
            description=(
                "JO stage + talent pool + AI Matching native 0-100 + interview/offering/onboard."
            ),
            depends_on=(),
            route_prefixes=("/recruitment", "/talentpool"),
            bundle="talent",
            meter="talent_active + match_credit",
        ),
        AppSpec(
            key="people_ops",
            name="People & Operations",
            emoji="👥",
            accent="green",
            description=(
                "Karyawan, kontrak, dokumen legal, BPJS+kartu+valid_until, "
                "asuransi polis+kartu (one-to-many), absensi, project placement, ESS, TTE."
            ),
            depends_on=(),
            route_prefixes=(
                "/employees",
                "/bpjs",
                "/me",
                "/notifications",
                "/esign",
                "/attendance",
            ),
            bundle="workforce",
            meter="employee_active",
        ),
        AppSpec(
            key="payroll",
            name="Payroll",
            emoji="💰",
            accent="emerald",
            description=(
                "Saltab grid, prorata, BPJS & PPh21 hitung, bukti potong. "
                "Tagih ke klien ada di Revenue."
            ),
            depends_on=(),
            route_prefixes=("/payroll",),
            bundle="revenue",
            meter="payslip",
        ),
        AppSpec(
            key="finance",
            name="Finance",
            emoji="💳",
            accent="orange",
            description=(
                "Invoice, faktur pajak e-Faktur DJP lengkap "
                "(lawan NPWP/DPP/kode/no_seri/NSFP/QR), outstanding/overdue, "
                "penagihan, cashflow."
            ),
            depends_on=(),
            route_prefixes=("/finance",),
            bundle="revenue",
            meter="invoice+faktur",
        ),
        AppSpec(
            key="accounting",
            name="Accounting",
            emoji="📊",
            accent="amber",
            description=(
                "Accurate.id lokal: CoA dinamis, jurnal memorial→posted, kas-bank, "
                "pembelian, aset, periode & tutup buku, laporan + AI."
            ),
            depends_on=(),
            route_prefixes=("/accounting",),
            bundle="govern",
            meter="flat",
        ),
        AppSpec(
            key="ai_addon",
            name="AI Add-on",
            emoji="✨",
            accent="violet",
            description=(
                "Chat AI @AEOS lintas app, RAG kontrak, forecast (matching sudah native di Talent)."
            ),
            depends_on=(),
            route_prefixes=("/ai",),
            bundle="addon",
            meter="token",
        ),
    )
}

TRIAL_DAYS = 14


@dataclass(frozen=True)
class BundleSpec:
    key: str
    name: str
    emoji: str
    apps: tuple[str, ...]
    description: str
    price_model: str


# ---- 4 Paket Komersial F + Foundation + Addon (PRD v3.0) ----
BUNDLE_REGISTRY: dict[str, BundleSpec] = {
    spec.key: spec
    for spec in (
        BundleSpec(
            key="foundation",
            name="Foundation",
            emoji="🏠",
            apps=(),
            description="Dashboard umum 8+1 widget, chat, pages — gratis selalu aktif.",
            price_model="gratis",
        ),
        BundleSpec(
            key="talent",
            name="Talent Cloud",
            emoji="🧲",
            apps=("sales_crm", "recruitment"),
            description=(
                "JO stage + talentpool + AI Matching native 0-100 + "
                "interview/offering/onboard. Metered: 15k/talent aktif + 2k/match. "
                "BUKAN jualan kandidat — talent milik tenant."
            ),
            price_model="15k/talent aktif + 2k/match",
        ),
        BundleSpec(
            key="workforce",
            name="Workforce Cloud",
            emoji="👥",
            apps=("people_ops",),
            description=(
                "Karyawan, kontrak, BPJS+kartu+valid_until, asuransi one-to-many "
                "polis+kartu, absensi, project placement, ESS, TTE. "
                "Horizontal — semua industri."
            ),
            price_model="10k/employee aktif",
        ),
        BundleSpec(
            key="revenue",
            name="Revenue Cloud",
            emoji="💳",
            apps=("payroll", "finance"),
            description=(
                "Payroll hitung + tagih (invoice, faktur DJP lengkap "
                "lawan NPWP/DPP/kode/no_seri/NSFP/QR, outstanding/overdue, cashflow). "
                "Metered: 5k/invoice + 8k/faktur + base 1jt."
            ),
            price_model="5k/invoice + 8k/faktur + base 1jt",
        ),
        BundleSpec(
            key="govern",
            name="Govern Cloud",
            emoji="📊",
            apps=("accounting",),
            description=(
                "Accurate.id lokal: CoA, jurnal, kas-bank, pembelian, aset, periode, laporan+AI."
            ),
            price_model="flat 5-7jt",
        ),
        BundleSpec(
            key="starter",
            name="Starter",
            emoji="🎯",
            apps=("people_ops",),
            description=(
                "Paket Starter = Foundation + Workforce — untuk outsourcing stabil (operate saja)."
            ),
            price_model="Workforce metered",
        ),
        BundleSpec(
            key="growth",
            name="Growth",
            emoji="🚀",
            apps=("sales_crm", "recruitment", "people_ops"),
            description="Starter + Talent — Growth = Workforce + Talent.",
            price_model="Workforce + Talent metered",
        ),
        BundleSpec(
            key="scale",
            name="Scale",
            emoji="💼",
            apps=("sales_crm", "recruitment", "people_ops", "payroll", "finance"),
            description="Growth + Revenue — Scale = Talent + Workforce + Revenue.",
            price_model="Talent + Workforce + Revenue metered",
        ),
        BundleSpec(
            key="enterprise",
            name="Enterprise",
            emoji="🏢",
            apps=("sales_crm", "recruitment", "people_ops", "payroll", "finance", "accounting"),
            description="Full — Scale + Govern.",
            price_model="Talent + Workforce + Revenue + Govern flat",
        ),
        BundleSpec(
            key="addon",
            name="AI Add-on",
            emoji="✨",
            apps=("ai_addon",),
            description="AI @AEOS lintas app (matching sudah native di Talent).",
            price_model="300/1k token",
        ),
    )
}


def app_keys() -> list[str]:
    return list(APP_REGISTRY)


def bundle_keys() -> list[str]:
    return list(BUNDLE_REGISTRY)


def bundle_for_app(app_key: str) -> str | None:
    spec = APP_REGISTRY.get(app_key)
    return spec.bundle if spec else None


def apps_for_bundle(bundle_key: str) -> list[str]:
    spec = BUNDLE_REGISTRY.get(bundle_key)
    return list(spec.apps) if spec else []


def app_for_path(path: str) -> str | None:
    """Kunci aplikasi untuk sebuah path API; None = kapabilitas foundation gratis."""
    for spec in APP_REGISTRY.values():
        for prefix in spec.route_prefixes:
            if path == prefix or path.startswith(prefix + "/"):
                return spec.key
    return None
