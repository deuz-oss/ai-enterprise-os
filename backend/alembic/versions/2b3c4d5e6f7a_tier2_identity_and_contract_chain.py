"""tier2_identity_fields_and_contract_chain

Tier 2 gap-fill dari audit MYOHRIS:

- `employees.kk_no/religion/blood_type/birthplace` -- 4 field identitas
  baru. `blood_type`/`birthplace` sebenarnya sudah ada di `candidates`
  sejak Fase 24, cuma belum pernah dibawa ke `employees` (sekarang disalin
  otomatis saat onboarding, lihat `hrd/service.py::onboard_from_placement`).
  `kk_no`/`religion` baru di kedua sisi.
- `employment_contracts.previous_contract_id` -- self-referencing FK,
  menandai satu kontrak sbg perpanjangan kontrak lain. NULL = kontrak awal.
  Dipakai rantai riwayat perpanjangan ("Extensions" MYOHRIS), lihat
  `hrd/service.py::extend_contract`.

Batch mode (pola sama migrasi Tier 1/kontak darurat sebelumnya) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: 2b3c4d5e6f7a
Revises: 9a1c2e3f4b5d
Create Date: 2026-09-14 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b3c4d5e6f7a"
down_revision: str | None = "9a1c2e3f4b5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("birthplace", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("kk_no", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("religion", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("blood_type", sa.String(length=5), nullable=True))

    with op.batch_alter_table("employment_contracts") as batch_op:
        batch_op.add_column(sa.Column("previous_contract_id", sa.CHAR(32), nullable=True))
        batch_op.create_foreign_key(
            "fk_employment_contracts_previous_contract_id",
            "employment_contracts",
            ["previous_contract_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("employment_contracts") as batch_op:
        batch_op.drop_constraint("fk_employment_contracts_previous_contract_id", type_="foreignkey")
        batch_op.drop_column("previous_contract_id")

    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("blood_type")
        batch_op.drop_column("religion")
        batch_op.drop_column("kk_no")
        batch_op.drop_column("birthplace")
