"""One-shot: migrasi tenant existing dari lisensi per-SKU (Opsi F) ke
langganan-tier + saldo kredit (Opsi G, Fase 28).

Jalankan SEKALI saat cutover, setelah kode guard subscription (Milestone 2)
sudah live. Logika (sudah diputuskan & didokumentasikan di PRD Fase 28,
bukan asumsi skrip ini):

1. Tenant dengan billing bypass aktif (`_is_billing_bypass` -- billing_mode
   "internal", atau "inherit" + APP_MODE global "internal") DILEWATI --
   mereka tidak pernah ditegakkan guard lisensi/subscription, jadi tidak
   butuh baris TenantSubscription untuk tetap bisa mengakses apa pun.
2. Untuk tenant komersial sisanya: hitung jumlah BUNDLE KOMERSIAL unik
   (talent/workforce/revenue/govern -- BUKAN termasuk foundation/addon/
   starter/growth/scale/enterprise) dari TenantAppLicense berstatus
   aktif/trial, via `core/apps.py::bundle_for_app()`.
3. 0 bundle aktif -> DILEWATI (foundation-only), tenant pilih tier sendiri
   lewat halaman Pembayaran kapan pun siap -- tidak dipaksa migrasi.
4. 1 bundle -> Tier 1, 2 bundle -> Tier 2, 3-4 bundle -> Tier 3.
5. Tidak ada grandfathering/masa transisi -- begitu di-apply, tenant itu
   langsung berlangganan Opsi G, guard lama (Opsi F) sudah dihapus total
   di Milestone 2 sehingga tidak ada "jalur ganda" untuk dijaga.

SENGAJA idempotent: tenant yang sudah punya `TenantSubscription` aktif
(hasil `--apply` sebelumnya, atau langganan asli lewat halaman Pembayaran)
dilewati -- aman dijalankan ulang tanpa risiko duplikasi.

Default `--dry-run` (tidak menulis apa pun) -- WAJIB `--apply` eksplisit
untuk benar-benar menulis, karena skrip ini menyentuh billing tenant asli.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from app.core.apps import bundle_for_app
from app.core.database import SessionLocal
from app.core.security import _is_billing_bypass
from app.core.tenancy import set_tenant
from app.modules.billing.models import (
    TIER_MONTHLY_FEE_IDR,
    SubscriptionStatus,
    SubscriptionTier,
    TenantBudgetCycle,
    TenantCreditAccount,
    TenantSubscription,
)
from app.modules.platform.models import LicenseStatus, Tenant, TenantAppLicense
from sqlalchemy import select

_COMMERCIAL_BUNDLES = {"talent", "workforce", "revenue", "govern"}
_ACTIVE_LICENSE_STATUSES = (LicenseStatus.active, LicenseStatus.trial)

_BUNDLE_COUNT_TO_TIER: dict[int, SubscriptionTier] = {
    1: SubscriptionTier.tier1,
    2: SubscriptionTier.tier2,
    3: SubscriptionTier.tier3,
    4: SubscriptionTier.tier3,
}


def migrate_tenant(db, tenant: Tenant, *, apply: bool) -> str:
    """Kembalikan satu baris log yang menjelaskan keputusan untuk tenant ini."""
    if _is_billing_bypass(db, tenant.id):
        return (
            f"[BYPASS]        {tenant.slug}: billing_mode={tenant.billing_mode!r} "
            "-- tidak ditegakkan guard, tidak perlu subscription"
        )

    # Skrip berdiri sendiri (bukan request handler) -- tidak ada konteks
    # tenant ambien untuk dipulihkan, cukup reset ke None di akhir.
    set_tenant(tenant.id)
    try:
        existing = db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant.id)
            .where(TenantSubscription.status == SubscriptionStatus.active)
        ).scalar_one_or_none()
        if existing is not None:
            return (
                f"[SUDAH ADA]     {tenant.slug}: sudah punya TenantSubscription aktif "
                f"({existing.tier.value}) -- dilewati"
            )

        licenses = (
            db.execute(
                select(TenantAppLicense)
                .where(TenantAppLicense.tenant_id == tenant.id)
                .where(TenantAppLicense.status.in_(_ACTIVE_LICENSE_STATUSES))
            )
            .scalars()
            .all()
        )
        bundles = {bundle_for_app(lic.app_key) for lic in licenses} & _COMMERCIAL_BUNDLES
        count = len(bundles)

        if count == 0:
            return (
                f"[FOUNDATION-ONLY] {tenant.slug}: 0 bundle komersial aktif -- dilewati, "
                "tenant pilih tier sendiri lewat halaman Pembayaran"
            )

        tier = _BUNDLE_COUNT_TO_TIER[count]
        fee = TIER_MONTHLY_FEE_IDR[tier]
        bundle_list = ", ".join(sorted(bundles))

        if not apply:
            return (
                f"[DRY-RUN]       {tenant.slug}: {count} bundle aktif ({bundle_list}) "
                f"-> {tier.value} (Rp{fee:,.0f}/bulan)"
            )

        subscription = TenantSubscription(
            tenant_id=tenant.id,
            tier=tier,
            monthly_fee=fee,
            included_budget=fee,
            status=SubscriptionStatus.active,
        )
        db.add(subscription)
        db.flush()

        today = date.today()
        db.add(
            TenantBudgetCycle(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                period_start=today,
                period_end=today + timedelta(days=30),
                included_budget=fee,
                consumed=0,
            )
        )
        db.add(TenantCreditAccount(tenant_id=tenant.id, balance=0))
        db.commit()
        return (
            f"[APPLIED]       {tenant.slug}: {count} bundle aktif ({bundle_list}) "
            f"-> {tier.value} (Rp{fee:,.0f}/bulan)"
        )
    finally:
        set_tenant(None)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Tulis perubahan sungguhan. Tanpa flag ini, skrip hanya mencetak rencana (dry-run).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenants = db.execute(select(Tenant)).scalars().all()
        mode = "APPLY (menulis perubahan)" if args.apply else "DRY-RUN (tidak menulis apa pun)"
        print(f"=== Migrasi Opsi F -> Opsi G -- mode: {mode} -- {len(tenants)} tenant ===\n")
        for tenant in tenants:
            print(migrate_tenant(db, tenant, apply=args.apply))
        if not args.apply:
            print("\nTidak ada perubahan ditulis. Jalankan ulang dengan --apply untuk menerapkan.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
