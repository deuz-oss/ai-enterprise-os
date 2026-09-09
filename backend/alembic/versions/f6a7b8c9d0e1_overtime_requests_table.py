"""overtime_requests_table

Tabel baru untuk pengajuan lembur karyawan lewat portal ESS (beda dari
`attendance_corrections` yang scope-nya koreksi angka SEBULAN yang sudah
tercatat -- ini pengajuan jam lembur baru per tanggal, mengikuti pola
`leave_requests`). RLS ditambahkan LANGSUNG di migrasi yang sama dengan
pembuatan tabel (pola yang sudah konsisten dipakai sejak
`9349e6c0fcac_offering_settings_table.py`).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "overtime_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("requested_hours", sa.Integer(), nullable=False),
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
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_overtime_requests_date"), "overtime_requests", ["date"], unique=False)
    op.create_index(
        op.f("ix_overtime_requests_employee_id"),
        "overtime_requests",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_overtime_requests_status"), "overtime_requests", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_overtime_requests_tenant_id"),
        "overtime_requests",
        ["tenant_id"],
        unique=False,
    )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE overtime_requests ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE overtime_requests FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON overtime_requests
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON overtime_requests"))
        op.execute(sa.text("ALTER TABLE overtime_requests NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE overtime_requests DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_overtime_requests_tenant_id"), table_name="overtime_requests")
    op.drop_index(op.f("ix_overtime_requests_status"), table_name="overtime_requests")
    op.drop_index(op.f("ix_overtime_requests_employee_id"), table_name="overtime_requests")
    op.drop_index(op.f("ix_overtime_requests_date"), table_name="overtime_requests")
    op.drop_table("overtime_requests")
