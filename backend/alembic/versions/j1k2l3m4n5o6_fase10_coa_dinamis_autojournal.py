"""Fase 10: bagan akun dinamis, periode, memorial/posted, auto-journal rules

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-08-25 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j1k2l3m4n5o6"
down_revision: str | None = "i0j1k2l3m4n5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.modules.accounting.coa_template import DEFAULT_COA, DEFAULT_RULES

    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_code", sa.String(length=20), nullable=True),
        sa.Column(
            "group_type",
            sa.Enum(
                "aset_lancar",
                "aset_tetap",
                "liabilitas_pendek",
                "liabilitas_panjang",
                "ekuitas",
                "pendapatan",
                "hpp",
                "beban_usaha",
                "beban_lain",
                "pendapatan_lain",
                name="grouptype",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("normal_balance", sa.String(length=10), nullable=False),
        sa.Column("is_cash_bank", sa.Boolean(), nullable=False),
        sa.Column("is_control_ar_ap", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_account_tenant_code"),
    )
    op.create_index(op.f("ix_accounts_tenant_id"), "accounts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_accounts_code"), "accounts", ["code"], unique=False)
    op.create_index(op.f("ix_accounts_group_type"), "accounts", ["group_type"], unique=False)

    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("closed_by_id", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["closed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "year", "month", name="uq_period_month"),
    )
    op.create_index(
        op.f("ix_accounting_periods_year"), "accounting_periods", ["year"], unique=False
    )

    op.add_column(
        "journal_entries",
        sa.Column(
            "status",
            sa.Enum("memorial", "posted", name="journalentrystatus", native_enum=False, length=50),
            server_default="posted",
            nullable=False,
        ),
    )
    op.add_column(
        "journal_entries", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("journal_entries", sa.Column("event_code", sa.String(length=50), nullable=True))
    op.add_column(
        "journal_entries", sa.Column("source_ref_type", sa.String(length=50), nullable=True)
    )
    op.add_column("journal_entries", sa.Column("source_ref_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_journal_entries_status"), "journal_entries", ["status"], unique=False)
    op.create_index(
        op.f("ix_journal_entries_event_code"), "journal_entries", ["event_code"], unique=False
    )

    with op.batch_alter_table("journal_lines") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("client_dim_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("memo", sa.String(length=200), nullable=True))
        batch_op.create_foreign_key("fk_journal_lines_account", "accounts", ["account_id"], ["id"])
        batch_op.create_foreign_key(
            "fk_journal_lines_client_dim", "clients", ["client_dim_id"], ["id"]
        )
    op.create_index(
        op.f("ix_journal_lines_account_id"), "journal_lines", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_journal_lines_client_dim_id"), "journal_lines", ["client_dim_id"], unique=False
    )

    op.create_table(
        "journal_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_code", sa.String(length=50), nullable=False),
        sa.Column("debit_account_code", sa.String(length=20), nullable=False),
        sa.Column("credit_account_code", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_code", name="uq_rule_tenant_event"),
    )
    op.create_index(
        op.f("ix_journal_rules_event_code"), "journal_rules", ["event_code"], unique=False
    )
    # ---- Data migration ----
    # 1) Seed COA default untuk setiap tenant.
    # 2) Map journal_lines lama (account_code) → account_id dari COA tenant.
    # 3) Seed rules aktif untuk event default.
    conn = op.get_bind()
    import uuid

    tenants = [r[0] for r in conn.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    for tenant_id in tenants:
        tid = str(tenant_id)
        for code, name, group, normal, cash, ar_ap in DEFAULT_COA:
            conn.execute(
                sa.text(
                    "INSERT INTO accounts (id, tenant_id, code, name, group_type, normal_balance, "
                    "is_cash_bank, is_control_ar_ap, is_active) "
                    "VALUES (:id, :tid, :code, :name, :grp, :nb, :cash, :arap, 1)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tid,
                    "code": code,
                    "name": name,
                    "grp": group,
                    "nb": normal,
                    "cash": int(cash),
                    "arap": int(ar_ap),
                },
            )
        # Map baris jurnal lama ke akun COA berdasar kode (dalam tenant sama).
        conn.execute(
            sa.text(
                """
                UPDATE journal_lines
                SET account_id = (
                    SELECT a.id FROM accounts a
                    WHERE a.tenant_id = journal_lines.tenant_id
                      AND a.code = journal_lines.account_code
                    LIMIT 1
                )
                WHERE account_id IS NULL
                  AND tenant_id = :tid
                """
            ),
            {"tid": tid},
        )
        for event, d, c in DEFAULT_RULES:
            conn.execute(
                sa.text(
                    "INSERT INTO journal_rules (id, tenant_id, event_code, debit_account_code, "
                    "credit_account_code, is_active) "
                    "VALUES (:id, :tid, :ev, :d, :c, 1)"
                ),
                {"id": str(uuid.uuid4()), "tid": tid, "ev": event, "d": d, "c": c},
            )


def downgrade() -> None:
    op.drop_table("journal_rules")
    with op.batch_alter_table("journal_lines") as batch_op:
        batch_op.drop_constraint("fk_journal_lines_client_dim", type_="foreignkey")
        batch_op.drop_constraint("fk_journal_lines_account", type_="foreignkey")
    op.drop_index(op.f("ix_journal_lines_client_dim_id"), table_name="journal_lines")
    op.drop_index(op.f("ix_journal_lines_account_id"), table_name="journal_lines")
    with op.batch_alter_table("journal_lines") as batch_op:
        batch_op.drop_column("memo")
        batch_op.drop_column("client_dim_id")
        batch_op.drop_column("account_id")
    op.drop_index(op.f("ix_journal_entries_event_code"), table_name="journal_entries")
    op.drop_index(op.f("ix_journal_entries_status"), table_name="journal_entries")
    with op.batch_alter_table("journal_entries") as batch_op:
        batch_op.drop_column("source_ref_id")
        batch_op.drop_column("source_ref_type")
        batch_op.drop_column("event_code")
        batch_op.drop_column("posted_at")
        batch_op.drop_column("status")
    op.drop_table("accounting_periods")
    op.drop_table("accounts")
