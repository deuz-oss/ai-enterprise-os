"""kolom user_id karyawan untuk akun self-service portal

Revision ID: a7f2d94c1e58
Revises: 03c4cecd231b
Create Date: 2026-08-24 12:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7f2d94c1e58"
down_revision: str | None = "03c4cecd231b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Akun login self-service (role karyawan) tertaut satu-satu ke data karyawan.
    # Batch mode agar ALTER ber-constraint juga jalan di SQLite.
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key("fk_employees_user_id_users", "users", ["user_id"], ["id"])
        batch_op.create_unique_constraint("uq_employees_user_id", ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_constraint("uq_employees_user_id", type_="unique")
        batch_op.drop_constraint("fk_employees_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")
