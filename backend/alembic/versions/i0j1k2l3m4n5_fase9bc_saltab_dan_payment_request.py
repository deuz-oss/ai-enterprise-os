"""Fase 9b-c: payslip_components (Saltab) + payment_requests

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-08-25 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i0j1k2l3m4n5"
down_revision: str | None = "h9i0j1k2l3m4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payslip_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("payslip_id", sa.Uuid(), nullable=False),
        sa.Column(
            "ctype",
            sa.Enum("earnings", "deduction", "passthrough", name="payslipcomponenttype", native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["payslip_id"], ["payslips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payslip_components_tenant_id"), "payslip_components", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_payslip_components_payslip_id"), "payslip_components", ["payslip_id"], unique=False
    )
    op.create_index(
        op.f("ix_payslip_components_ctype"), "payslip_components", ["ctype"], unique=False
    )

    op.create_table(
        "payment_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("pr_number", sa.String(length=50), nullable=False),
        sa.Column("pr_type", sa.String(length=20), nullable=False),
        sa.Column("payroll_run_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "diajukan",
                "menunggu_atasan",
                "disetujui_atasan",
                "dieksekusi",
                "ditolak",
                name="paymentrequeststatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(length=500), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["payroll_runs.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["executed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "pr_number", name="uq_pr_tenant_number"),
    )
    op.create_index(
        op.f("ix_payment_requests_tenant_id"), "payment_requests", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_payment_requests_payroll_run_id"),
        "payment_requests",
        ["payroll_run_id"],
        unique=False,
    )
    op.create_index(op.f("ix_payment_requests_status"), "payment_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("payment_requests")
    op.drop_table("payslip_components")
