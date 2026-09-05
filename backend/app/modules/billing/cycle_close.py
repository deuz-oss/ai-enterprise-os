"""Penutupan siklus anggaran & debit periodik (Fase 28).

Dua metrik pemakaian (talent aktif, employee aktif) berbasis SNAPSHOT --
tidak ada event diskrit untuk dikaitkan debit real-time seperti
match_executed/invoice_issued/tax_invoice_sent/ai_usage (lihat
`billing/service.py`). Keduanya ditagih di sini, sekali per penutupan
siklus, terhadap `TenantBudgetCycle` yang BARU dibuka -- bukan yang
ditutup -- supaya "pemakaian bulan ini" berarti kondisi di awal bulan
berjalan, konsisten dengan cara `platform/usage.py::compute_usage()`
menghitungnya untuk laporan Opsi F lama.

Tidak ada scheduler in-process di codebase ini (dikonfirmasi saat
perencanaan Fase 28) -- `close_cycle_for_tenant` dipanggil dari dua jalur:
1. `POST /platform/internal/run-cycle-charge`, dipicu scheduler OS
   eksternal (cron/Task Scheduler) di luar proses backend.
2. Safety-net di `core/security.py::require_active_subscription()` --
   kalau siklus tenant sudah lewat tanggal tutup tapi trigger eksternal
   terlewat, ditutup inline saat request berikutnya masuk. Korektnes
   TIDAK bergantung pada scheduler eksternal benar-benar jalan.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import get_tenant, set_tenant
from app.modules.billing.models import SubscriptionStatus, TenantBudgetCycle, TenantSubscription
from app.modules.billing.service import _get_open_cycle, record_credit_transaction


def _add_months(d: date, months: int) -> date:
    """Math bulan manual tanpa dependency baru -- sama persis pola
    `recruitment/service.py::_add_months`, sengaja tidak diimpor lintas
    modul karena terlalu kecil untuk dijadikan utilitas bersama."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def close_cycle_for_tenant(db: Session, tenant_id: UUID) -> TenantBudgetCycle | None:
    """Tutup `TenantBudgetCycle` yang sudah lewat `period_end` lalu buka
    yang berikutnya, mendebit biaya snapshot dari cycle baru.

    No-op (return None) bila: tenant tanpa `TenantSubscription` aktif,
    tenant belum punya cycle sama sekali (cycle pertama dibuat saat
    subscribe -- Milestone 7 -- bukan tanggung jawab fungsi ini), atau
    cycle yang ada belum lewat `period_end`.
    """
    subscription = db.execute(
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
        .where(TenantSubscription.status == SubscriptionStatus.active)
    ).scalar_one_or_none()
    if subscription is None:
        return None

    cycle = _get_open_cycle(db, tenant_id)
    if cycle is None:
        return None
    if cycle.period_end >= date.today():
        return None

    previous_tenant = get_tenant()
    set_tenant(tenant_id)
    try:
        cycle.closed_at = datetime.now(UTC)
        period_start = cycle.period_end + timedelta(days=1)
        period_end = _add_months(period_start, 1) - timedelta(days=1)

        new_cycle = TenantBudgetCycle(
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            period_start=period_start,
            period_end=period_end,
            included_budget=subscription.included_budget,
            consumed=0,
        )
        db.add(new_cycle)
        db.flush()

        from app.modules.platform.usage import _employee_active_count, _talent_active_count

        talent_qty = _talent_active_count(db, tenant_id)
        if talent_qty:
            record_credit_transaction(
                db,
                amount=-(talent_qty * 15_000),
                ref_event="cycle_close.talent_active",
                allow_negative=True,
            )
        emp_qty = _employee_active_count(db, tenant_id)
        if emp_qty:
            record_credit_transaction(
                db,
                amount=-(emp_qty * 10_000),
                ref_event="cycle_close.employee_active",
                allow_negative=True,
            )

        db.commit()
        db.refresh(new_cycle)
        return new_cycle
    finally:
        set_tenant(previous_tenant)


def run_cycle_charge_for_all_tenants(db: Session) -> list[UUID]:
    """Loop semua tenant, tutup cycle yang sudah lewat waktunya (no-op untuk
    tenant tanpa subscription aktif). Dipanggil dari
    `POST /platform/internal/run-cycle-charge`. Return daftar tenant_id yang
    cycle-nya benar-benar ditutup (bukan semua tenant yang dicek -- kebanyakan
    no-op tiap hari).

    Query daftar tenant lewat tabel `tenants` (tanpa `tenant_id`/RLS -- aman
    di-scan lintas tenant), BUKAN `TenantSubscription` (RLS-protected):
    tanpa `set_tenant()` aktif, query ke tabel ber-RLS di konteks
    platform_admin akan pulang nol baris (`app.current_tenant` kosong tidak
    cocok tenant manapun) -- lihat catatan kejujuran RLS di `core/tenancy.py`.
    Konteks tenant di-set per-iterasi SEBELUM query TenantSubscription di
    dalam `close_cycle_for_tenant`, supaya RLS lolos untuk tenant yang
    sedang diproses.
    """
    from app.modules.platform.models import Tenant

    previous_tenant = get_tenant()
    tenant_ids = [row[0] for row in db.execute(select(Tenant.id)).all()]
    closed: list[UUID] = []
    try:
        for tenant_id in tenant_ids:
            set_tenant(tenant_id)
            if close_cycle_for_tenant(db, tenant_id) is not None:
                closed.append(tenant_id)
    finally:
        set_tenant(previous_tenant)
    return closed
