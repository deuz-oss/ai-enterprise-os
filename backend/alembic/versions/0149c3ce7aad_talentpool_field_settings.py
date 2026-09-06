"""talentpool_field_settings_table

Revision ID: 0149c3ce7aad
Revises: 519f65da4618
Create Date: 2026-09-06 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0149c3ce7aad"
down_revision: str | None = "519f65da4618"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "talentpool_field_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("visible_fields_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_talentpool_field_settings_tenant_id"),
        "talentpool_field_settings",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_talentpool_field_settings_tenant_id"), table_name="talentpool_field_settings"
    )
    op.drop_table("talentpool_field_settings")
