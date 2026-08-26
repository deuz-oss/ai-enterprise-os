"""Fase 9 penutup: rantai approval PR multi-level per tenant

Tabel pr_approval_steps (config tahap) + pr_approvals (jejak keputusan).

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-08-26 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n4o5p6q7r8s9"
down_revision: str | None = "m3n4o5p6q7r8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pr_approval_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("approver_role", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "seq", name="uq_pr_step_tenant_seq"),
    )
    op.create_index(
        op.f("ix_pr_approval_steps_tenant_id"), "pr_approval_steps", ["tenant_id"], unique=False
    )
    op.create_index(op.f("ix_pr_approval_steps_seq"), "pr_approval_steps", ["seq"], unique=False)

    op.create_table(
        "pr_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("payment_request_id", sa.Uuid(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"]),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_approvals_tenant_id"), "pr_approvals", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_pr_approvals_payment_request_id"),
        "pr_approvals",
        ["payment_request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("pr_approvals")
    op.drop_table("pr_approval_steps")
