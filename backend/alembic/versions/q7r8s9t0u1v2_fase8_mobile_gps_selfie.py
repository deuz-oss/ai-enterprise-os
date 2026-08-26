"""Fase 8 lanjutan: mobile GPS+selfie absensi (kolom geo & selfie)

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-08-26 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q7r8s9t0u1v2"
down_revision: str | None = "p6q7r8s9t0u1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attendance_records") as batch:
        batch.add_column(sa.Column("clock_in_geo", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("clock_out_geo", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("clock_in_selfie_key", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("clock_out_selfie_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("attendance_records") as batch:
        batch.drop_column("clock_out_selfie_key")
        batch.drop_column("clock_in_selfie_key")
        batch.drop_column("clock_out_geo")
        batch.drop_column("clock_in_geo")
