"""users.token_version: revokasi token JWT saat password berubah.

Token membawa klaim `tv`; versi dinaikkan saat ganti/reset password sehingga
token lama ditolak. Default 0 = token lama tanpa klaim tetap berlaku, jadi
rilis ini tidak memaksa semua user logout.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
