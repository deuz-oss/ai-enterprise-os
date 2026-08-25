"""kolom lampiran pada leave_requests (mis. surat dokter)

Revision ID: e8b4c7d1a952
Revises: d6e3f2a8c471
Create Date: 2026-08-24 16:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8b4c7d1a952"
down_revision: str | None = "d6e3f2a8c471"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tanpa constraint → ADD COLUMN biasa aman di SQLite & PostgreSQL.
    op.add_column("leave_requests", sa.Column("object_key", sa.String(length=500), nullable=True))
    op.add_column("leave_requests", sa.Column("file_name", sa.String(length=255), nullable=True))
    op.add_column("leave_requests", sa.Column("mime_type", sa.String(length=120), nullable=True))
    op.add_column(
        "leave_requests",
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    with op.batch_alter_table("leave_requests") as batch_op:
        batch_op.drop_column("file_size")
        batch_op.drop_column("mime_type")
        batch_op.drop_column("file_name")
        batch_op.drop_column("object_key")
