"""Fase 8: tabel attendance_records + kolom employees.employment_type

Revision ID: b4d5e6f7a8b9
Revises: a1b2c3d4e5f6
Create Date: 2026-08-25 07:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4d5e6f7a8b9"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "hadir",
                "terlambat",
                "izin",
                "sakit",
                "cuti",
                "alpa",
                "libur",
                "dinas_luar",
                name="attendancestatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("clock_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clock_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "overtime_hours", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "source",
            sa.Enum(
                "manual",
                "impor",
                "mobile",
                "ess",
                name="attendancesource",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "date", name="uq_attendance_record_day"),
    )
    op.create_index(
        op.f("ix_attendance_records_tenant_id"),
        "attendance_records",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_records_employee_id"),
        "attendance_records",
        ["employee_id"],
        unique=False,
    )
    op.create_index(op.f("ix_attendance_records_date"), "attendance_records", ["date"], unique=False)
    op.create_index(
        op.f("ix_attendance_records_status"), "attendance_records", ["status"], unique=False
    )

    # Jenis kepegawaian untuk validasi dua jalur absensi & payrol.
    # Default 'eksternal' sesuai bisnis inti outsourcing; karyawan internal
    # diubah manual oleh HR setelah migrasi.
    op.add_column(
        "employees",
        sa.Column(
            "employment_type",
            sa.Enum("internal", "eksternal", name="employmenttype", native_enum=False, length=50),
            server_default="eksternal",
            nullable=False,
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("employment_type")
    op.drop_table("attendance_records")
