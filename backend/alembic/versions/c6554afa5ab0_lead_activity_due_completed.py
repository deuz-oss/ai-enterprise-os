"""lead_activity_due_completed

Fase 43 -- follow-up terjadwal & reminder lintas lead, terinspirasi
`Activity.dueAt`/`completedAt` di CRM open-source trycompai/crm. Dua
kolom baru di `lead_activities`:

- `due_at`: kapan follow-up ini harus dikerjakan (opsional, bisa dipasang
  ke aktivitas tipe apa pun, bukan cuma tipe "tugas" baru).
- `completed_at`: null berarti masih pending/jatuh tempo.

`activity_type` tetap kolom VARCHAR polos tanpa CHECK constraint DB
(dikonfirmasi lewat schema live -- `Enum(..., native_enum=False)` di
model ini tidak merender CHECK di SQLite), jadi menambah nilai enum baru
("tugas") di sisi Python TIDAK butuh migrasi kolom terpisah.

Batch mode (pola sama `bd33f16a67b6_shift_and_address_fields.py`) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: c6554afa5ab0
Revises: ee9837fbe8de
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6554afa5ab0"
down_revision: str | None = "ee9837fbe8de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lead_activities") as batch:
        batch.add_column(sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lead_activities") as batch:
        batch.drop_column("completed_at")
        batch.drop_column("due_at")
