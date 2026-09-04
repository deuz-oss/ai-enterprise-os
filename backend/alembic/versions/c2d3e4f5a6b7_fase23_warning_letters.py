"""Fase 23 butir 3: tabel warning_letters -- Surat Peringatan (SP1/SP2/SP3)
per karyawan, pola sama seperti employee_documents.

Revision ID: c2d3e4f5a6b7
Revises: 81374fa44242
Create Date: 2026-09-04 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "81374fa44242"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "warning_letters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("letter_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("issued_at", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("object_key", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_warning_letters_tenant_id"), "warning_letters", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_warning_letters_employee_id"), "warning_letters", ["employee_id"], unique=False
    )
    op.create_index(
        op.f("ix_warning_letters_valid_until"), "warning_letters", ["valid_until"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_warning_letters_valid_until"), table_name="warning_letters")
    op.drop_index(op.f("ix_warning_letters_employee_id"), table_name="warning_letters")
    op.drop_index(op.f("ix_warning_letters_tenant_id"), table_name="warning_letters")
    op.drop_table("warning_letters")
