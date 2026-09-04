"""Fase 20 item 3: tabel agreement_templates -- template visual Agreement,
sama pola dengan quotation_templates (tabel sendiri per jenis dokumen).

Revision ID: 548cf9057559
Revises: 77bf2cae8e08
Create Date: 2026-09-04 07:53:37.988471
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "548cf9057559"
down_revision: str | None = "77bf2cae8e08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agreement_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("field_schema", sa.Text(), nullable=False),
        sa.Column("footer_text", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agreement_templates_tenant_id"), "agreement_templates", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agreement_templates_tenant_id"), table_name="agreement_templates")
    op.drop_table("agreement_templates")
