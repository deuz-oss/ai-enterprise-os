"""tabel attendance_corrections untuk koreksi absensi oleh karyawan

Revision ID: f9c2e6b8d314
Revises: e8b4c7d1a952
Create Date: 2026-08-24 17:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9c2e6b8d314"
down_revision: str | None = "e8b4c7d1a952"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("requested_present_days", sa.Integer(), nullable=False),
        sa.Column("requested_overtime_hours", sa.Integer(), nullable=False),
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
        op.f("ix_attendance_corrections_tenant_id"),
        "attendance_corrections",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_corrections_employee_id"),
        "attendance_corrections",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_corrections_year"), "attendance_corrections", ["year"], unique=False
    )
    op.create_index(
        op.f("ix_attendance_corrections_status"),
        "attendance_corrections",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_corrections_status"), table_name="attendance_corrections")
    op.drop_index(op.f("ix_attendance_corrections_year"), table_name="attendance_corrections")
    op.drop_index(
        op.f("ix_attendance_corrections_employee_id"), table_name="attendance_corrections"
    )
    op.drop_index(op.f("ix_attendance_corrections_tenant_id"), table_name="attendance_corrections")
    op.drop_table("attendance_corrections")
