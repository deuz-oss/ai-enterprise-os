"""Fase 10 lanjutan — tabel bank_transactions, purchase_bills, fixed_assets."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k2l3m4n5o6p7"
down_revision: str | None = "j1k2l3m4n5o6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_cols() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tx_date", sa.Date(), nullable=False),
        sa.Column(
            "tx_type",
            sa.Enum(
                "penerimaan", "pembayaran", "transfer_antar_rekening",
                name="banktxttype", native_enum=False, length=50,
            ),
            nullable=False,
        ),
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("counter_account_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        *_common_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["counter_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tx_date", "tx_type", "bank_account_id"):
        op.create_index(op.f(f"ix_bank_transactions_{col}"), "bank_transactions", [col], unique=False)

    op.create_table(
        "purchase_bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vendor_name", sa.String(length=255), nullable=False),
        sa.Column("bill_number", sa.String(length=100), nullable=True),
        sa.Column("expense_account_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("ppn_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("ppn_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("belum_dibayar", "dibayar", name="billstatus", native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column("received_journal_id", sa.Uuid(), nullable=True),
        sa.Column("paid_journal_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        *_common_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["expense_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["received_journal_id"], ["journal_entries.id"]),
        sa.ForeignKeyConstraint(["paid_journal_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("entry_date", "status", "expense_account_id"):
        op.create_index(op.f(f"ix_purchase_bills_{col}"), "purchase_bills", [col], unique=False)

    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_account_id", sa.Uuid(), nullable=False),
        sa.Column("accum_depreciation_account_id", sa.Uuid(), nullable=False),
        sa.Column("depreciation_expense_account_id", sa.Uuid(), nullable=False),
        sa.Column("funding_account_id", sa.Uuid(), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("accumulated_depreciation", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("monthly_depreciation", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("last_depreciated_ym", sa.String(length=7), nullable=True),
        sa.Column("disposed_at", sa.Date(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        *_common_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["asset_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["accum_depreciation_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["depreciation_expense_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["funding_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("asset_account_id", "acquisition_date"):
        op.create_index(op.f(f"ix_fixed_assets_{col}"), "fixed_assets", [col], unique=False)


def downgrade() -> None:
    op.drop_table("fixed_assets")
    op.drop_table("purchase_bills")
    op.drop_table("bank_transactions")
