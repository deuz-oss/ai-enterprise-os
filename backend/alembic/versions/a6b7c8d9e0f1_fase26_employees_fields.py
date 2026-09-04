"""Fase 26: employees field tambahan hasil review Employee Detail --
grade/level, emergency contact terstruktur, alamat KTP vs domisili
terpisah (JSON), payroll_locked.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-09-04 16:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch:
        batch.add_column(sa.Column("grade", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("level", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("emergency_contact_name", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("emergency_contact_relation", sa.String(length=100), nullable=True)
        )
        batch.add_column(sa.Column("emergency_contact_phone", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("citizen_address_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("residential_address_json", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "payroll_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")
            )
        )
        batch.add_column(sa.Column("payroll_locked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch:
        batch.drop_column("payroll_locked_at")
        batch.drop_column("payroll_locked")
        batch.drop_column("residential_address_json")
        batch.drop_column("citizen_address_json")
        batch.drop_column("emergency_contact_phone")
        batch.drop_column("emergency_contact_relation")
        batch.drop_column("emergency_contact_name")
        batch.drop_column("level")
        batch.drop_column("grade")
