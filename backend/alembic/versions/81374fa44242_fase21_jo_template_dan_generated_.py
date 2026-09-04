"""Fase 21 item 4: tabel job_order_templates + job_orders.
generated_document_object_key/generated_document_at -- generate dokumen JO
dari template, reuse rendering PDF Fase 20.

Revision ID: 81374fa44242
Revises: 65e9eb9bf191
Create Date: 2026-09-04 10:19:23.534269
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "81374fa44242"
down_revision: str | None = "65e9eb9bf191"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_order_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
        op.f("ix_job_order_templates_tenant_id"), "job_order_templates", ["tenant_id"], unique=False
    )

    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(
            sa.Column("generated_document_object_key", sa.String(length=500), nullable=True)
        )
        batch.add_column(
            sa.Column("generated_document_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("generated_document_at")
        batch.drop_column("generated_document_object_key")
    op.drop_index(op.f("ix_job_order_templates_tenant_id"), table_name="job_order_templates")
    op.drop_table("job_order_templates")
