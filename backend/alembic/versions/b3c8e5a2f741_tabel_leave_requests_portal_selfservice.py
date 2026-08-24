"""tabel leave_requests untuk portal self-service karyawan

Revision ID: b3c8e5a2f741
Revises: a7f2d94c1e58
Create Date: 2026-08-24 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c8e5a2f741"
down_revision: str | None = "a7f2d94c1e58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "employee_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "leave_type",
            sa.Enum(
                "cuti_tahunan",
                "izin",
                "sakit",
                "cuti_tak_berbayar",
                name="leavetype",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "menunggu",
                "disetujui",
                "ditolak",
                "dibatalkan",
                name="leavestatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_leave_requests_tenant_id"), "leave_requests", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_leave_requests_employee_id"), "leave_requests", ["employee_id"], unique=False
    )
    op.create_index(op.f("ix_leave_requests_status"), "leave_requests", ["status"], unique=False)
    op.create_index(
        op.f("ix_leave_requests_start_date"), "leave_requests", ["start_date"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_leave_requests_start_date"), table_name="leave_requests")
    op.drop_index(op.f("ix_leave_requests_status"), table_name="leave_requests")
    op.drop_index(op.f("ix_leave_requests_employee_id"), table_name="leave_requests")
    op.drop_index(op.f("ix_leave_requests_tenant_id"), table_name="leave_requests")
    op.drop_table("leave_requests")
