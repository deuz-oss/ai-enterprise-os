"""lead_sales_ops_fields

Fase 42 -- bundel field sales-ops kecil di `leads`, terinspirasi
`Deal.stageChangedAt`/`closedReason`/`expectedCloseDate`/`lastActivityAt`
di CRM open-source trycompai/crm:

- `expected_close_date`: target tanggal closing, diisi manual staf.
- `stage_changed_at`: kapan terakhir kali `stage` berubah (auto).
- `closed_reason`: alasan menang/kalah saat stage deal/gagal (manual).
- `last_activity_at`: kapan terakhir ada aktivitas tercatat (auto).

Baris lama di-backfill `stage_changed_at`/`last_activity_at` = `created_at`
supaya tidak NULL untuk lead yang sudah ada -- lebih akurat daripada NULL
literal karena lead itu memang "berubah tahap" pertama kali saat dibuat.

Batch mode (pola sama `bd33f16a67b6_shift_and_address_fields.py`) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: ee9837fbe8de
Revises: b89a4b594ad5
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ee9837fbe8de"
down_revision: str | None = "b89a4b594ad5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("expected_close_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("stage_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("closed_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            "UPDATE leads SET stage_changed_at = created_at, last_activity_at = created_at "
            "WHERE stage_changed_at IS NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("last_activity_at")
        batch.drop_column("closed_reason")
        batch.drop_column("stage_changed_at")
        batch.drop_column("expected_close_date")
