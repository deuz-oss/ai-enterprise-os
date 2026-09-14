"""employee_personal_data_fields

Tier 1 gap-fill dari audit MYOHRIS (kartu "Personal Data"): lima field baru
pada `employees`, semuanya nullable --

- `email`: email pribadi/kantor karyawan (beda dari email akun login
  `user_id`, yang mana pun boleh kosong independen dari yang lain).
- `birthdate`, `gender`, `education`, `current_position`: disalin sekali
  dari `Candidate` saat onboarding (`onboard_from_placement`), field-field
  ini SUDAH ADA di `candidates` -- cuma belum pernah dibawa ke `employees`.
  `current_position` = jabatan SEBELUM direkrut (snapshot kandidat), bukan
  jabatan di perusahaan ini sekarang.

Batch mode (pola sama `bd33f16a67b6_shift_and_address_fields.py`) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: 7fffe60cc637
Revises: 17ea218b3149
Create Date: 2026-09-14 16:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7fffe60cc637"
down_revision: str | None = "17ea218b3149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("birthdate", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("gender", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("education", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("current_position", sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("current_position")
        batch_op.drop_column("education")
        batch_op.drop_column("gender")
        batch_op.drop_column("birthdate")
        batch_op.drop_column("email")
