"""Scope direktori chat (PRD §9.2) — satu sumber aturan "siapa boleh melihat siapa".

Dipakai bersama oleh autocomplete mention (`search_users_for_mention`),
validasi mention per pesan (`_validate_mentions`), validasi anggota saat
membuat channel (`create_channel`), serta presence & typing di WebSocket.
Jangan menduplikasi logika cohort di tempat lain: panggil
`resolve_directory_scope`.

Aturan (sengaja SAMA dengan perilaku sebelum ekstraksi):
- Staff (role selain `karyawan`): seluruh user tenant.
- Karyawan outsourcing: sesama karyawan yang Employee-nya ter-placement di
  klien yang sama (status placement apa pun) + seluruh user Ops tenant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid


@dataclass(frozen=True)
class DirectoryScope:
    """Himpunan user yang boleh dilihat seorang viewer di tenant-nya sendiri.

    `all_tenant=True` berarti seluruh user tenant viewer (staff). Batas tenant
    TIDAK dicek di sini — pemanggil wajib memastikan subjek satu tenant
    (registry WS dikunci per tenant; REST memfilter `tenant_id`).
    """

    all_tenant: bool
    user_ids: frozenset[str] = field(default_factory=frozenset)

    def can_see(self, user_id: object) -> bool:
        return self.all_tenant or str(user_id) in self.user_ids


def resolve_directory_scope(db: Session, user) -> DirectoryScope:
    """Hitung scope direktori `user` (PRD §9.2). Aman dipanggil tanpa konteks
    tenant: semua query di sini difilter `tenant_id` secara eksplisit."""
    from app.modules.chat.service import _get_ops_user_ids, is_staff

    if is_staff(user):
        return DirectoryScope(all_tenant=True)

    from app.modules.hrd.models import Employee
    from app.modules.recruitment.models import JobOrder, Placement

    tenant_id = user.tenant_id
    cohort: set[str] = {str(uid) for uid in _get_ops_user_ids(db, tenant_id)}
    emp = db.execute(
        select(Employee).where(
            Employee.user_id == parse_uuid(str(user.id)),
            Employee.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if emp is not None and emp.placement_id:
        placement = db.get(Placement, emp.placement_id)
        jo = db.get(JobOrder, placement.job_order_id) if placement is not None else None
        if jo is not None and jo.tenant_id == tenant_id:
            # Semua karyawan yang ditempatkan di klien yang sama.
            cohort_user_ids = db.execute(
                select(Employee.user_id)
                .join(Placement, Employee.placement_id == Placement.id)
                .join(JobOrder, Placement.job_order_id == JobOrder.id)
                .where(JobOrder.client_id == jo.client_id)
                .where(Employee.tenant_id == tenant_id)
                .where(Employee.user_id.is_not(None))
            ).scalars()
            cohort.update(str(uid) for uid in cohort_user_ids)
    return DirectoryScope(all_tenant=False, user_ids=frozenset(cohort))
