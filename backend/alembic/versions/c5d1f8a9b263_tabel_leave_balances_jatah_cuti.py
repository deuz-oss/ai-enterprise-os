"""tabel leave_balances untuk jatah cuti tahunan

Revision ID: c5d1f8a9b263
Revises: b3c8e5a2f741
Create Date: 2026-08-24 14:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d1f8a9b263"
down_revision: str | None = "b3c8e5a2f741"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("used_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "year", name="uq_leave_balance_period"),
    )
    op.create_index(
        op.f("ix_leave_balances_tenant_id"), "leave_balances", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_leave_balances_employee_id"), "leave_balances", ["employee_id"], unique=False
    )
    op.create_index(op.f("ix_leave_balances_year"), "leave_balances", ["year"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leave_balances_year"), table_name="leave_balances")
    op.drop_index(op.f("ix_leave_balances_employee_id"), table_name="leave_balances")
    op.drop_index(op.f("ix_leave_balances_tenant_id"), table_name="leave_balances")
    op.drop_table("leave_balances")
