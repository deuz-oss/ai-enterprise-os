"""tier3_division_position_contract_type

Tier 3 gap-fill dari audit MYOHRIS (tanpa field manager -- disengaja
dilewati atas permintaan user):

- `employees.division`/`position` -- live field, bukan cuma snapshot
  before/after di `employee_movements`. Di-backfill dari mutasi TERAKHIR
  tiap karyawan yang punya `new_division`/`new_position` terisi (kalau ada)
  supaya data historis tidak hilang.
- `employment_contracts.contract_type` (pkwt/pkwtt, nullable) -- dasar
  validasi batas total durasi PKWT 5 tahun (UU Cipta Kerja) di
  `hrd/service.py::create_contract`.

Batch mode (pola sama migrasi Tier 1/2 sebelumnya) supaya ALTER TABLE juga
jalan di SQLite.

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-09-14 20:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c4d5e6f7a8b"
down_revision: str | None = "2b3c4d5e6f7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("division", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("position", sa.String(length=120), nullable=True))

    # Backfill dari mutasi terakhir yang punya new_division/new_position --
    # no-op kalau belum ada baris employee_movements (kondisi paling umum).
    op.execute(
        """
        UPDATE employees
        SET division = (
            SELECT m.new_division FROM employee_movements m
            WHERE m.employee_id = employees.id
              AND m.new_division IS NOT NULL AND m.new_division != ''
            ORDER BY m.effective_date DESC, m.created_at DESC LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM employee_movements m
            WHERE m.employee_id = employees.id
              AND m.new_division IS NOT NULL AND m.new_division != ''
        )
        """
    )
    op.execute(
        """
        UPDATE employees
        SET position = (
            SELECT m.new_position FROM employee_movements m
            WHERE m.employee_id = employees.id
              AND m.new_position IS NOT NULL AND m.new_position != ''
            ORDER BY m.effective_date DESC, m.created_at DESC LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM employee_movements m
            WHERE m.employee_id = employees.id
              AND m.new_position IS NOT NULL AND m.new_position != ''
        )
        """
    )

    with op.batch_alter_table("employment_contracts") as batch_op:
        batch_op.add_column(sa.Column("contract_type", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employment_contracts") as batch_op:
        batch_op.drop_column("contract_type")

    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("position")
        batch_op.drop_column("division")
