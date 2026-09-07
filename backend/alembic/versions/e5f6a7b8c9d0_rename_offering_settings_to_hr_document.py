"""rename_offering_settings_to_hr_document

`offering_settings` digeneralisasi jadi `hr_document_settings` -- setting
ini sekarang dipakai ULANG oleh email kontrak kerja
(`hrd.service.send_contract_for_signature`), bukan cuma surat penawaran
lagi (lihat docstring `HrDocumentSettings` di recruitment/models.py).
Rename murni, tidak ada perubahan kolom -- RLS policy ikut tabel (Postgres
melacak lewat OID, bukan nama), tidak perlu drop/recreate. Index PERLU
di-rename manual (tidak ikut otomatis seperti policy) supaya cocok dengan
nama yang dihasilkan naming convention model (`ix_hr_document_settings_
tenant_id`), jaga `test_upgrade_head_identik_dengan_create_all` tetap hijau.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-07 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.rename_table("offering_settings", "hr_document_settings")
    if _is_pg():
        op.execute(
            sa.text(
                "ALTER INDEX ix_offering_settings_tenant_id "
                "RENAME TO ix_hr_document_settings_tenant_id"
            )
        )


def downgrade() -> None:
    if _is_pg():
        op.execute(
            sa.text(
                "ALTER INDEX ix_hr_document_settings_tenant_id "
                "RENAME TO ix_offering_settings_tenant_id"
            )
        )
    op.rename_table("hr_document_settings", "offering_settings")
