"""Fase 28: model billing Opsi G -- tenant_subscriptions, tenant_budget_cycles,
tenant_credit_accounts, credit_transactions. Menggantikan penegakan lisensi
per-SKU (Opsi F) dengan langganan-tier + saldo kredit; tabel Opsi F lama
(`tenant_app_licenses`, `Tenant.billing_mode`) TIDAK dihapus di sini, tetap
ada untuk keperluan historis/rollback per ADR-0007 poin 3.

Revision ID: d0e1f2a3b4c5
Revises: c8d9e0f1a2b3
Create Date: 2026-09-05 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = [
    "tenant_subscriptions",
    "tenant_budget_cycles",
    "tenant_credit_accounts",
    "credit_transactions",
]


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable_rls(table: str) -> None:
    # Pola persis g8h9i0j1k2l3_extend_rls_coverage.py -- kegagalan pembuatan
    # policy tidak boleh menggagalkan migrasi.
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = 'public' AND tablename = '{table}'
                      AND policyname = 'tenant_isolation'
                ) THEN
                    CREATE POLICY tenant_isolation ON {table}
                    USING (tenant_id::text = current_setting('app.current_tenant', true))
                    WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
                END IF;
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END $$;
            """
        )
    )


def _disable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))


def upgrade() -> None:
    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("monthly_fee", sa.Numeric(14, 2), nullable=False),
        sa.Column("included_budget", sa.Numeric(14, 2), nullable=False),
        sa.Column("cycle_start_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="aktif"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenant_subscriptions_tenant_id"), "tenant_subscriptions", ["tenant_id"]
    )
    op.create_index(op.f("ix_tenant_subscriptions_status"), "tenant_subscriptions", ["status"])

    op.create_table(
        "tenant_budget_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("included_budget", sa.Numeric(14, 2), nullable=False),
        sa.Column("consumed", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenant_budget_cycles_tenant_id"), "tenant_budget_cycles", ["tenant_id"]
    )
    op.create_index(
        op.f("ix_tenant_budget_cycles_subscription_id"), "tenant_budget_cycles", ["subscription_id"]
    )
    op.create_index(
        "ix_budget_cycle_tenant_period", "tenant_budget_cycles", ["tenant_id", "period_start"]
    )

    op.create_table(
        "tenant_credit_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "auto_reload_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("auto_reload_threshold", sa.Numeric(14, 2), nullable=True),
        sa.Column("auto_reload_amount", sa.Numeric(14, 2), nullable=False, server_default="100000"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_credit_account_tenant"),
    )
    op.create_index(
        op.f("ix_tenant_credit_accounts_tenant_id"), "tenant_credit_accounts", ["tenant_id"]
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("ref_event", sa.String(length=80), nullable=False),
        sa.Column("ref_entity_type", sa.String(length=50), nullable=True),
        sa.Column("ref_entity_id", sa.String(length=100), nullable=True),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_transactions_tenant_id"), "credit_transactions", ["tenant_id"])
    op.create_index(op.f("ix_credit_transactions_type"), "credit_transactions", ["type"])
    op.create_index(
        "ix_credit_tx_tenant_created", "credit_transactions", ["tenant_id", "created_at"]
    )

    if _is_pg():
        for table in NEW_TABLES:
            _enable_rls(table)


def downgrade() -> None:
    if _is_pg():
        for table in NEW_TABLES:
            _disable_rls(table)

    op.drop_index("ix_credit_tx_tenant_created", table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_type"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_tenant_id"), table_name="credit_transactions")
    op.drop_table("credit_transactions")

    op.drop_index(op.f("ix_tenant_credit_accounts_tenant_id"), table_name="tenant_credit_accounts")
    op.drop_table("tenant_credit_accounts")

    op.drop_index("ix_budget_cycle_tenant_period", table_name="tenant_budget_cycles")
    op.drop_index(
        op.f("ix_tenant_budget_cycles_subscription_id"), table_name="tenant_budget_cycles"
    )
    op.drop_index(op.f("ix_tenant_budget_cycles_tenant_id"), table_name="tenant_budget_cycles")
    op.drop_table("tenant_budget_cycles")

    op.drop_index(op.f("ix_tenant_subscriptions_status"), table_name="tenant_subscriptions")
    op.drop_index(op.f("ix_tenant_subscriptions_tenant_id"), table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")
