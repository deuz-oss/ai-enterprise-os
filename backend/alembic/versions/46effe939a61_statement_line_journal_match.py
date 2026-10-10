"""bank_statement_lines: cocokkan ke jurnal kas/bank (bukan hanya transaksi bank).

Pelunasan invoice/bill, eksekusi payment request, dan aset memposting jurnal
kas/bank tanpa BankTransaction, sehingga baris rekening koran untuknya tidak
pernah bisa dicocokkan.

Revision ID: 46effe939a61
Revises: c3d4e5f6a7b8
Create Date: 2026-10-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "46effe939a61"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bank_statement_lines") as batch:
        batch.add_column(sa.Column("suggested_journal_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("matched_journal_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_bank_statement_lines_suggested_journal_id",
            "journal_entries",
            ["suggested_journal_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_bank_statement_lines_matched_journal_id",
            "journal_entries",
            ["matched_journal_id"],
            ["id"],
        )
    op.create_index(
        op.f("ix_bank_statement_lines_matched_journal_id"),
        "bank_statement_lines",
        ["matched_journal_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bank_statement_lines_matched_journal_id"), table_name="bank_statement_lines"
    )
    with op.batch_alter_table("bank_statement_lines") as batch:
        batch.drop_constraint("fk_bank_statement_lines_matched_journal_id", type_="foreignkey")
        batch.drop_constraint("fk_bank_statement_lines_suggested_journal_id", type_="foreignkey")
        batch.drop_column("matched_journal_id")
        batch.drop_column("suggested_journal_id")
