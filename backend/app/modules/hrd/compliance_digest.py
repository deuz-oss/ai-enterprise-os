"""Digest kepatuhan mingguan: kontrak & BPJS (peluang AI #4 audit 2026-10-08).

Isi (deterministik, tiap butir dengan aksi yang disarankan):
- kontrak karyawan aktif yang berakhir <= 30 hari lagi;
- kontrak yang SUDAH lewat tetapi karyawannya masih aktif dan tidak ada
  perpanjangan (karyawan bekerja tanpa kontrak berlaku);
- karyawan aktif tanpa nomor BPJS Kesehatan dan/atau Ketenagakerjaan.

Pengiriman mengikuti keputusan Fase 28 (tidak ada scheduler in-process):
- `POST /platform/internal/run-weekly-digest` dipicu cron OS eksternal;
- safety-net: saat admin/HR memuat badge notifikasi, digest minggu berjalan
  dibuat bila belum ada -- jadi benar walau cron tidak terpasang.
Idempoten per tenant per minggu ISO: penandanya notifikasi itu sendiri
(`entity_type = "compliance_digest:<tahun>-W<minggu>"`), tanpa tabel baru.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.hrd.models import Employee, EmployeeStatus, EmploymentContract

ENDING_WITHIN_DAYS = 30
MAX_ITEMS = 50
DIGEST_CATEGORY = "compliance"


def week_key(today: date) -> str:
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def _missing(value: str | None) -> bool:
    return not (value or "").strip()


def build_digest(db: Session, today: date | None = None) -> dict:
    """Susun digest untuk tenant aktif (konteks tenant harus sudah disetel)."""
    from app.modules.hrd.service import expiring_contracts

    today = today or date.today()

    ending = [
        {
            "employee_id": str(c["employee_id"]),
            "employee_name": c["employee_name"],
            "contract_no": c["contract_no"],
            "end_date": c["end_date"].isoformat(),
            "days_left": c["days_left"],
            "action": (
                "Perpanjang kontrak atau siapkan proses akhir hubungan kerja"
                if c["days_left"] > 7
                else "Segera putuskan: perpanjang atau akhiri (≤ 7 hari)"
            ),
        }
        for c in expiring_contracts(db, ENDING_WITHIN_DAYS)
    ]

    # Kontrak terakhir (bukan yang sudah diperpanjang) yang sudah lewat,
    # untuk karyawan aktif yang tidak punya kontrak lain yang masih berlaku.
    superseded = select(EmploymentContract.previous_contract_id).where(
        EmploymentContract.previous_contract_id.is_not(None)
    )
    still_valid = select(EmploymentContract.employee_id).where(
        or_(EmploymentContract.end_date.is_(None), EmploymentContract.end_date >= today)
    )
    lapsed_rows = db.execute(
        select(EmploymentContract, Employee)
        .join(Employee, EmploymentContract.employee_id == Employee.id)
        .where(
            Employee.status == EmployeeStatus.active,
            EmploymentContract.end_date.is_not(None),
            EmploymentContract.end_date < today,
            EmploymentContract.id.not_in(superseded),
            Employee.id.not_in(still_valid),
        )
        .order_by(EmploymentContract.end_date)
    ).all()
    seen: set[UUID] = set()
    lapsed = []
    for contract, employee in lapsed_rows:
        if employee.id in seen or contract.end_date is None:
            continue
        seen.add(employee.id)
        lapsed.append(
            {
                "employee_id": str(employee.id),
                "employee_name": employee.full_name,
                "contract_no": contract.contract_no,
                "end_date": contract.end_date.isoformat(),
                "days_overdue": (today - contract.end_date).days,
                "action": "Masih aktif tanpa kontrak berlaku: perpanjang atau nonaktifkan",
            }
        )

    bpjs_missing = []
    for employee in db.execute(
        select(Employee)
        .where(Employee.status == EmployeeStatus.active)
        .order_by(Employee.full_name)
    ).scalars():
        gaps = [
            label
            for label, value in (
                ("Kesehatan", employee.bpjs_kesehatan_no),
                ("Ketenagakerjaan", employee.bpjs_ketenagakerjaan_no),
            )
            if _missing(value)
        ]
        if gaps:
            bpjs_missing.append(
                {
                    "employee_id": str(employee.id),
                    "employee_name": employee.full_name,
                    "missing": gaps,
                    "action": f"Daftarkan / isi nomor BPJS {' & '.join(gaps)}",
                }
            )

    return {
        "week": week_key(today),
        "generated_on": today.isoformat(),
        "counts": {
            "contracts_ending": len(ending),
            "contracts_lapsed": len(lapsed),
            "bpjs_missing": len(bpjs_missing),
        },
        "contracts_ending": ending[:MAX_ITEMS],
        "contracts_lapsed": lapsed[:MAX_ITEMS],
        "bpjs_missing": bpjs_missing[:MAX_ITEMS],
    }


def _summary(digest: dict) -> tuple[str, str]:
    c = digest["counts"]
    if not any(c.values()):
        return (
            f"Kepatuhan {digest['week']}: semua beres",
            "Tidak ada kontrak yang segera berakhir/lewat dan BPJS karyawan aktif lengkap.",
        )
    parts = []
    if c["contracts_lapsed"]:
        parts.append(f"{c['contracts_lapsed']} kontrak sudah lewat")
    if c["contracts_ending"]:
        parts.append(f"{c['contracts_ending']} kontrak berakhir ≤ {ENDING_WITHIN_DAYS} hari")
    if c["bpjs_missing"]:
        parts.append(f"{c['bpjs_missing']} karyawan belum lengkap BPJS")
    return (
        f"Kepatuhan {digest['week']}: " + ", ".join(parts),
        "Buka Karyawan → Kepatuhan minggu ini untuk rincian dan aksi.",
    )


def send_weekly_digest(db: Session, today: date | None = None) -> int:
    """Kirim digest minggu ini ke admin & HR tenant aktif; idempoten per minggu.

    Return jumlah penerima (0 bila sudah terkirim minggu ini / tanpa tenant).
    """
    from app.core.tenancy import get_tenant
    from app.modules.auth.models import User, UserRole
    from app.modules.notifications.models import Notification
    from app.modules.notifications.service import notify

    tenant_id = get_tenant()
    if tenant_id is None:
        return 0
    today = today or date.today()
    marker = f"compliance_digest:{week_key(today)}"
    if db.execute(
        select(Notification.id).where(Notification.entity_type == marker).limit(1)
    ).first():
        return 0
    recipients = (
        db.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.role.in_([UserRole.admin, UserRole.hr]),
            )
        )
        .scalars()
        .all()
    )
    if not recipients:
        return 0
    title, body = _summary(build_digest(db, today))
    for uid in recipients:
        notify(
            db,
            user_id=uid,
            title=title,
            body=body,
            category=DIGEST_CATEGORY,
            entity_type=marker,
        )
    return len(recipients)


def run_weekly_digest_for_all_tenants(db: Session, today: date | None = None) -> dict:
    """Dipanggil `POST /platform/internal/run-weekly-digest` (cron OS)."""
    from app.core.tenancy import tenant_context
    from app.modules.platform.models import Tenant, TenantStatus

    sent: dict[str, int] = {}
    active = select(Tenant.id).where(Tenant.status == TenantStatus.active)
    for (tenant_id,) in db.execute(active).all():
        with tenant_context(tenant_id):
            count = send_weekly_digest(db, today)
        if count:
            sent[str(tenant_id)] = count
    return sent
