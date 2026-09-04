"""Fase 20 item 2: tabel quotations (state machine draft -> pending_approval
-> approved/rejected -> sent -> accepted_by_client/expired).

Revision ID: 77bf2cae8e08
Revises: 309cbf108910
Create Date: 2026-09-04 07:25:45.950207
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "77bf2cae8e08"
down_revision: str | None = "309cbf108910"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("field_values", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_approval",
                "approved",
                "rejected",
                "sent",
                "accepted_by_client",
                "expired",
                name="quotationstatus",
                native_enum=False,
                length=30,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("object_key", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["quotation_templates.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quotations_tenant_id"), "quotations", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_quotations_lead_id"), "quotations", ["lead_id"], unique=False)
    op.create_index(op.f("ix_quotations_status"), "quotations", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quotations_status"), table_name="quotations")
    op.drop_index(op.f("ix_quotations_lead_id"), table_name="quotations")
    op.drop_index(op.f("ix_quotations_tenant_id"), table_name="quotations")
    op.drop_table("quotations")
