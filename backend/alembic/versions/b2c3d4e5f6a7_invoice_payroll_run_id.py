"""invoices.payroll_run_id: run payroll sumber tagihan.

Dulu invoice tidak menyimpan run-nya, sehingga rekonsiliasi invoice ↔ absensi
harus menebak run dan generate invoice error saat satu periode punya lebih dari
satu run. Invoice lama tetap NULL (rekonsiliasi memilih ulang run-nya).

Revision ID: b2c3d4e5f6a7
Revises: ad1e2f3a4b5c
Create Date: 2026-10-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "ad1e2f3a4b5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("payroll_run_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_invoices_payroll_run_id", "payroll_runs", ["payroll_run_id"], ["id"]
        )
    op.create_index(
        op.f("ix_invoices_payroll_run_id"), "invoices", ["payroll_run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_invoices_payroll_run_id"), table_name="invoices")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("fk_invoices_payroll_run_id", type_="foreignkey")
        batch.drop_column("payroll_run_id")
