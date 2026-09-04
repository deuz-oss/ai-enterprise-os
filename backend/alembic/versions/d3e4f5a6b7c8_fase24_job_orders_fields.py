"""Fase 24: job_orders field tambahan hasil audit MYOHRIS -- remote,
office_address, experience_level, contract_detail, industry, position,
level, package_detail.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-04 16:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(
            sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
        batch.add_column(sa.Column("office_address", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("experience_level", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("contract_detail", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("industry", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("position", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("level", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("package_detail", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("package_detail")
        batch.drop_column("level")
        batch.drop_column("position")
        batch.drop_column("industry")
        batch.drop_column("contract_detail")
        batch.drop_column("experience_level")
        batch.drop_column("office_address")
        batch.drop_column("remote")
