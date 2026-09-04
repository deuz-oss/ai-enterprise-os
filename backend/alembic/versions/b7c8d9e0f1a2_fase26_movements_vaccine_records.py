"""Fase 26: tabel employee_movements (riwayat mutasi/promosi/demosi) dan
vaccine_records (riwayat vaksinasi) -- konsep baru, belum ada padanan.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-09-04 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("previous_grade", sa.String(length=50), nullable=True),
        sa.Column("new_grade", sa.String(length=50), nullable=True),
        sa.Column("previous_level", sa.String(length=50), nullable=True),
        sa.Column("new_level", sa.String(length=50), nullable=True),
        sa.Column("previous_division", sa.String(length=120), nullable=True),
        sa.Column("new_division", sa.String(length=120), nullable=True),
        sa.Column("previous_position", sa.String(length=120), nullable=True),
        sa.Column("new_position", sa.String(length=120), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_movements_tenant_id"), "employee_movements", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_employee_movements_employee_id"),
        "employee_movements",
        ["employee_id"],
        unique=False,
    )

    op.create_table(
        "vaccine_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("vaccine_name", sa.String(length=120), nullable=False),
        sa.Column("dose_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("vaccinated_at", sa.Date(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("object_key", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vaccine_records_tenant_id"), "vaccine_records", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_vaccine_records_employee_id"), "vaccine_records", ["employee_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vaccine_records_employee_id"), table_name="vaccine_records")
    op.drop_index(op.f("ix_vaccine_records_tenant_id"), table_name="vaccine_records")
    op.drop_table("vaccine_records")

    op.drop_index(op.f("ix_employee_movements_employee_id"), table_name="employee_movements")
    op.drop_index(op.f("ix_employee_movements_tenant_id"), table_name="employee_movements")
    op.drop_table("employee_movements")
