"""salary_holds_table

Revision ID: 519f65da4618
Revises: f2a3b4c5d6e7
Create Date: 2026-09-06 09:14:21.799492

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "519f65da4618"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "salary_holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("held_payslip_id", sa.Uuid(), nullable=False),
        sa.Column("released_payslip_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("held", "released", name="salaryholdstatus", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "held_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["held_payslip_id"], ["payslips.id"]),
        sa.ForeignKeyConstraint(["released_payslip_id"], ["payslips.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_salary_holds_employee_id"), "salary_holds", ["employee_id"], unique=False
    )
    op.create_index(
        op.f("ix_salary_holds_held_payslip_id"), "salary_holds", ["held_payslip_id"], unique=False
    )
    op.create_index(op.f("ix_salary_holds_status"), "salary_holds", ["status"], unique=False)
    op.create_index(op.f("ix_salary_holds_tenant_id"), "salary_holds", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_salary_holds_tenant_id"), table_name="salary_holds")
    op.drop_index(op.f("ix_salary_holds_status"), table_name="salary_holds")
    op.drop_index(op.f("ix_salary_holds_held_payslip_id"), table_name="salary_holds")
    op.drop_index(op.f("ix_salary_holds_employee_id"), table_name="salary_holds")
    op.drop_table("salary_holds")
