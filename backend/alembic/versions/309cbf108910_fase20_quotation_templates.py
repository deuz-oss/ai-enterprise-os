"""Fase 20 item 2: tabel quotation_templates -- template visual quotation
(field_schema JSON), fondasi generator Quotation. Rendering PDF-nya generik
(`presales/rendering.py`), dipakai ulang nanti oleh Agreement (item 3) dan
dokumen Job Order (Fase 21 item 4).

Revision ID: 309cbf108910
Revises: b0946b216ff2
Create Date: 2026-09-04 07:03:35.679795
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "309cbf108910"
down_revision: str | None = "b0946b216ff2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotation_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("field_schema", sa.Text(), nullable=False),
        sa.Column("footer_text", sa.String(length=255), nullable=True),
        sa.Column("accent_color", sa.String(length=9), nullable=False, server_default="#0f172a"),
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
        op.f("ix_quotation_templates_tenant_id"), "quotation_templates", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quotation_templates_tenant_id"), table_name="quotation_templates")
    op.drop_table("quotation_templates")
