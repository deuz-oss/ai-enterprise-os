"""Fase 20 item 3: tabel agreements (state machine draft -> internal_review
-> approved/declined -> sent -> signed/declined lewat esign item 4).

Revision ID: be1bef15724c
Revises: 548cf9057559
Create Date: 2026-09-04 07:53:53.699022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "be1bef15724c"
down_revision: str | None = "548cf9057559"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agreements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("field_values", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "internal_review",
                "approved",
                "sent",
                "signed",
                "declined",
                "expired",
                name="agreementstatus",
                native_enum=False,
                length=30,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["template_id"], ["agreement_templates.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agreements_tenant_id"), "agreements", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_agreements_lead_id"), "agreements", ["lead_id"], unique=False)
    op.create_index(op.f("ix_agreements_status"), "agreements", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agreements_status"), table_name="agreements")
    op.drop_index(op.f("ix_agreements_lead_id"), table_name="agreements")
    op.drop_index(op.f("ix_agreements_tenant_id"), table_name="agreements")
    op.drop_table("agreements")
