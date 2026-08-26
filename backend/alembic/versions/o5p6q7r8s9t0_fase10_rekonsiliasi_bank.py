"""Fase 10 sisa AI: bank_statement_lines (rekonsiliasi bank cerdas)

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-08-26 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o5p6q7r8s9t0"
down_revision: str | None = "n4o5p6q7r8s9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("tx_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("amount_in", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amount_out", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "belum_cocok",
                "usulan",
                "tercocok",
                "diabaikan",
                name="statementlinestatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("suggested_tx_id", sa.Uuid(), nullable=True),
        sa.Column("match_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("match_reason", sa.String(length=500), nullable=True),
        sa.Column("matched_tx_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["suggested_tx_id"], ["bank_transactions.id"]),
        sa.ForeignKeyConstraint(["matched_tx_id"], ["bank_transactions.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bank_statement_lines_tenant_id"),
        "bank_statement_lines",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(op.f("ix_bank_statement_lines_tx_date"), "bank_statement_lines", ["tx_date"])
    op.create_index(
        op.f("ix_bank_statement_lines_status"), "bank_statement_lines", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_table("bank_statement_lines")
