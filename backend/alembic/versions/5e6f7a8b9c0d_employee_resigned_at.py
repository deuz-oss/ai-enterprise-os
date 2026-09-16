"""employee_resigned_at

Dashboard "sinyal bisnis apa yang belum muncul" (audit desain 2026-09-15):
turnover karyawan cuma bisa dihitung statis (total resign sepanjang masa)
karena tidak ada kapan status berubah jadi resign. Tambah
`employees.resigned_at`, diisi otomatis oleh `hrd/service.py::update_employee`
saat status bertransisi ke resigned (dikosongkan lagi kalau rehire) --
lihat komentar di models.py. Tidak ada backfill UPDATE utk baris lama
yang sudah berstatus resign sebelum kolom ini ada -- turnover-per-periode
baru akurat mulai dari sini, bukan direkonstruksi dari data historis yang
memang tidak pernah dicatat.

Batch mode (pola sama migrasi Tier 1-3/bank_account_validation) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-09-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e6f7a8b9c0d"
down_revision: str | None = "4d5e6f7a8b9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("resigned_at", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("resigned_at")
