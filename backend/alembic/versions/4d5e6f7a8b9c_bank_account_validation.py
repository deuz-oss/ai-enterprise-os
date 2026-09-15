"""bank_account_validation

Integrasi validasi rekening bank karyawan (provider api.co.id, lihat
`app/core/bank_validation/`):

- `employees.bank_code`: slug bank kanonik provider (mis. "bank_bri"),
  BERDAMPINGAN dgn `bank_name` teks bebas lama -- TIDAK di-backfill, data
  lama (16 baris) dibiarkan apa adanya sampai HR pilih ulang bank lewat
  dropdown baru di Employee Detail.
- `employees.bank_account_verified/_name/_at`: server-computed-only,
  diisi otomatis saat `bank_code`+`bank_account` disimpan & fitur aktif
  (`BANK_VALIDATION_PROVIDER` terisi) -- lihat
  `hrd/service.py::_revalidate_bank_account`.

Tidak ada backfill UPDATE -- semua baris baru default null/false, tidak
ada data historis yang direkonstruksi.

Batch mode (pola sama migrasi Tier 1-3 sebelumnya) supaya ALTER TABLE
juga jalan di SQLite.

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-09-15 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d5e6f7a8b9c"
down_revision: str | None = "3c4d5e6f7a8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("bank_code", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column(
                "bank_account_verified", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column("bank_account_verified_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("bank_account_verified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("bank_account_verified_at")
        batch_op.drop_column("bank_account_verified_name")
        batch_op.drop_column("bank_account_verified")
        batch_op.drop_column("bank_code")
