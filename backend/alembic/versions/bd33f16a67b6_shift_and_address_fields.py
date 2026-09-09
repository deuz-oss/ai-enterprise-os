"""shift_and_address_fields

Fase 36 -- dua field baru pada tabel existing:
- `employees.shift_start_time`/`shift_end_time` (Time, nullable): shift
  default tetap per karyawan, diatur HR, ditampilkan di halaman Absensi
  Portal Saya. Bukan jadwal rotasi -- satu shift tetap saja.
- `attendance_records.clock_in_address`/`clock_out_address` (String,
  nullable): hasil reverse geocoding best-effort dari koordinat GPS,
  diresolve sekali saat clock-in/out (lihat `core/geocoding.py`).

Batch mode (pola sama `a7f2d94c1e58_kolom_user_id_karyawan_portal_selfservice.py`)
supaya ALTER TABLE juga jalan di SQLite.

Revision ID: bd33f16a67b6
Revises: 4eae323acbfb
Create Date: 2026-09-08 15:37:51.273407

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bd33f16a67b6"
down_revision: str | None = "4eae323acbfb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("shift_start_time", sa.Time(), nullable=True))
        batch_op.add_column(sa.Column("shift_end_time", sa.Time(), nullable=True))
    with op.batch_alter_table("attendance_records") as batch_op:
        batch_op.add_column(sa.Column("clock_in_address", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("clock_out_address", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("attendance_records") as batch_op:
        batch_op.drop_column("clock_out_address")
        batch_op.drop_column("clock_in_address")
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("shift_end_time")
        batch_op.drop_column("shift_start_time")
