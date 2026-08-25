"""Registry aplikasi portofolio (single source of truth Fase 7).

Setiap entri memetakan satu aplikasi komersial ke modul kode dan prefix
route-nya. Dependensi antar aplikasi mengikuti PRD §4; guard lisensi di
`main.py` memakai `app_for_path()` sehingga endpoint tanpa lisensi
mengembalikan 403.

Prefix yang TIDAK terdaftar di sini (auth, platform, overview, files,
health, /apps itu sendiri) adalah kapabilitas platform gratis.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    key: str
    name: str
    emoji: str
    accent: str  # kelas warna aksen untuk frontend
    description: str
    depends_on: tuple[str, ...]
    route_prefixes: tuple[str, ...]


APP_REGISTRY: dict[str, AppSpec] = {
    spec.key: spec
    for spec in (
        AppSpec(
            key="sales_crm",
            name="Sales CRM",
            emoji="🎯",
            accent="blue",
            description="Lead/pipeline, aktivitas, konversi klien, dokumen legalitas.",
            depends_on=(),
            route_prefixes=("/leads", "/clients"),
        ),
        AppSpec(
            key="recruitment",
            name="Recruitment",
            emoji="🧲",
            accent="purple",
            description="Job order, kandidat, seleksi, placement.",
            depends_on=("sales_crm",),
            route_prefixes=("/recruitment",),
        ),
        AppSpec(
            key="hr_payroll",
            name="HR & Payroll",
            emoji="💼",
            accent="green",
            description=(
                "Karyawan internal, kontrak, dokumen HR, absensi internal, "
                "payrol internal, ESS portal."
            ),
            depends_on=(),
            route_prefixes=("/employees", "/payroll", "/bpjs", "/me"),
        ),
        AppSpec(
            key="operations_billing",
            name="Operations & Billing",
            emoji="🏗️",
            accent="orange",
            description=(
                "Monitoring penempatan, absensi outsourcing, payrol proyek, "
                "approval klien, Payment Request, draft invoice."
            ),
            depends_on=("sales_crm", "recruitment"),
            route_prefixes=("/finance",),
        ),
        AppSpec(
            key="finance_accounting",
            name="Finance & Accounting",
            emoji="📊",
            accent="amber",
            description=(
                "Bagan akun dinamis, jurnal & memorial, kas-bank, periode & "
                "tutup buku, laporan lengkap + AI akuntansi."
            ),
            depends_on=("sales_crm",),
            route_prefixes=("/accounting",),
        ),
        AppSpec(
            key="esign",
            name="E-Sign",
            emoji="✒️",
            accent="red",
            description="TTE tersertifikasi untuk kontrak kerja & PKS.",
            depends_on=("hr_payroll",),
            route_prefixes=("/esign",),
        ),
        AppSpec(
            key="ai_addon",
            name="AI Add-on",
            emoji="✨",
            accent="violet",
            description="Screening CV, matching, RAG kontrak, forecast, insight lintas app.",
            depends_on=(),
            route_prefixes=("/ai",),
        ),
    )
}

TRIAL_DAYS = 14


def app_keys() -> list[str]:
    return list(APP_REGISTRY)


def app_for_path(path: str) -> str | None:
    """Kunci aplikasi untuk sebuah path API; None = kapabilitas gratis."""
    for spec in APP_REGISTRY.values():
        for prefix in spec.route_prefixes:
            if path == prefix or path.startswith(prefix + "/"):
                return spec.key
    return None
