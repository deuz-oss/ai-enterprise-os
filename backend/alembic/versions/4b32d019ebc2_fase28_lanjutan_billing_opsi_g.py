"""Fase 28 lanjutan: billing Opsi G -- metode bayar tersimpan, auto-reload,
kwitansi resmi, langganan tahunan, renewal & aturan gagal bayar.

Rencana: docs/03-architecture/billing-opsi-g-completion.md (§3-§4).

HANYA berisi perubahan billing (autogenerate juga mendeteksi drift index lama
di tabel lain -- sengaja TIDAK diserap ke revisi ini).

- Tabel tenant baru (`tenant_billing_profiles`, `tenant_payment_methods`,
  `payment_charges`, `billing_receipts`) ber-TenantMixin dan diberi RLS
  FORCE di PostgreSQL: webhook menurunkan tenant dari `reference_id` buatan
  Aeos lalu `set_tenant()` SEBELUM lookup, jadi tidak perlu pengecualian RLS.
- Tabel platform-level tanpa `tenant_id` (`billing_receipt_sequences`,
  `payment_webhook_events`) tanpa RLS -- di luar cakupan
  `test_rls_coverage.py` (yang hanya memeriksa tabel ber-tenant_id NOT NULL).
- Kolom baru di tabel lama lewat `batch_alter_table` (SQLite tidak mendukung
  ALTER ADD COLUMN dengan FK). Backfill portabel SQLite/PostgreSQL.

Revision ID: 4b32d019ebc2
Revises: 57b5ffb1923e
Create Date: 2026-10-31 07:12:05.637921
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b32d019ebc2"
down_revision: str | None = "57b5ffb1923e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = [
    "tenant_billing_profiles",
    "tenant_payment_methods",
    "payment_charges",
    "billing_receipts",
]
_NOW = sa.text("(CURRENT_TIMESTAMP)")


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable_rls(table: str) -> None:
    # Pola persis f2a3b4c5d6e7_extend_rls_coverage_2.py.
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
                RAISE NOTICE 'RLS policy untuk {table} dilewati: %', SQLERRM;
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
        "billing_receipt_sequences",
        sa.Column("year", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("last_number", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("dedup_key", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "dedup_key", name="uq_webhook_event_dedup"),
    )
    op.create_table(
        "tenant_billing_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("npwp", sa.String(length=22), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("billing_email", sa.String(length=255), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_billing_profile_tenant"),
    )
    op.create_index(
        op.f("ix_tenant_billing_profiles_tenant_id"), "tenant_billing_profiles", ["tenant_id"]
    )
    op.create_table(
        "tenant_payment_methods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_payment_method_id", sa.String(length=120), nullable=False),
        sa.Column("reference_id", sa.String(length=160), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("card_brand", sa.String(length=30), nullable=True),
        sa.Column("card_last4", sa.String(length=4), nullable=True),
        sa.Column("card_exp_month", sa.SmallInteger(), nullable=True),
        sa.Column("card_exp_year", sa.SmallInteger(), nullable=True),
        sa.Column("ewallet_account_masked", sa.String(length=40), nullable=True),
        sa.Column("failure_reason", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_payment_method_id", name="uq_payment_method_provider_id"
        ),
        sa.UniqueConstraint("reference_id", name="uq_payment_method_reference"),
    )
    op.create_index(
        "ix_payment_method_tenant_status", "tenant_payment_methods", ["tenant_id", "status"]
    )
    op.create_index(
        op.f("ix_tenant_payment_methods_tenant_id"), "tenant_payment_methods", ["tenant_id"]
    )
    op.create_table(
        "payment_charges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("payment_method_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("provider_charge_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_no", sa.SmallInteger(), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.String(length=300), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["payment_method_id"], ["tenant_payment_methods.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_charge_idem"),
        sa.UniqueConstraint("provider_charge_id", name="uq_payment_charge_provider"),
    )
    op.create_index("ix_payment_charge_tenant_status", "payment_charges", ["tenant_id", "status"])
    op.create_index(op.f("ix_payment_charges_tenant_id"), "payment_charges", ["tenant_id"])
    op.create_table(
        "billing_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_number", sa.String(length=40), nullable=False),
        sa.Column("receipt_year", sa.SmallInteger(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("payment_intent_id", sa.Uuid(), nullable=True),
        sa.Column("payment_charge_id", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seller_snapshot_json", sa.Text(), nullable=True),
        sa.Column("buyer_snapshot_json", sa.Text(), nullable=False),
        sa.Column("lines_json", sa.Text(), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("dpp", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("ppn_rate", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("ppn_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("payment_method_label", sa.String(length=80), nullable=False),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("pdf_object_key", sa.String(length=500), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["payment_charge_id"], ["payment_charges.id"]),
        sa.ForeignKeyConstraint(["payment_intent_id"], ["payment_intents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_charge_id", name="uq_receipt_charge"),
        sa.UniqueConstraint("payment_intent_id", name="uq_receipt_intent"),
        sa.UniqueConstraint("receipt_number", name="uq_receipt_number"),
        sa.UniqueConstraint("receipt_year", "sequence_no", name="uq_receipt_year_seq"),
    )
    op.create_index(op.f("ix_billing_receipts_tenant_id"), "billing_receipts", ["tenant_id"])
    op.create_index("ix_receipt_tenant_issued", "billing_receipts", ["tenant_id", "issued_at"])

    with op.batch_alter_table("tenant_subscriptions") as batch:
        batch.add_column(
            sa.Column(
                "billing_period", sa.String(length=20), server_default="monthly", nullable=False
            )
        )
        batch.add_column(sa.Column("period_fee", sa.Numeric(14, 2), nullable=True))
        batch.add_column(
            sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("current_period_end", sa.Date(), nullable=True))
        batch.add_column(sa.Column("past_due_since", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "renewal_attempt_count", sa.SmallInteger(), server_default="0", nullable=False
            )
        )
        batch.add_column(
            sa.Column("next_renewal_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
    # Backfill: langganan lama = bulanan, period_fee = monthly_fee, masa bayar =
    # akhir siklus terbuka (subquery berkorelasi, portabel SQLite/PostgreSQL).
    op.execute(sa.text("UPDATE tenant_subscriptions SET period_fee = monthly_fee"))
    op.execute(
        sa.text(
            "UPDATE tenant_subscriptions SET current_period_end = ("
            "SELECT MAX(c.period_end) FROM tenant_budget_cycles c "
            "WHERE c.subscription_id = tenant_subscriptions.id AND c.closed_at IS NULL) "
            "WHERE status = 'aktif'"
        )
    )
    with op.batch_alter_table("tenant_subscriptions") as batch:
        batch.alter_column("period_fee", existing_type=sa.Numeric(14, 2), nullable=False)

    with op.batch_alter_table("tenant_credit_accounts") as batch:
        batch.add_column(sa.Column("default_payment_method_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("auto_reload_in_flight_charge_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column(
                "auto_reload_failure_count", sa.SmallInteger(), server_default="0", nullable=False
            )
        )
        batch.add_column(
            sa.Column("auto_reload_next_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("auto_reload_last_error", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("metered_blocked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("metered_block_reason", sa.String(length=40), nullable=True))
        batch.create_foreign_key(
            "fk_credit_account_default_pm",
            "tenant_payment_methods",
            ["default_payment_method_id"],
            ["id"],
        )

    with op.batch_alter_table("payment_intents") as batch:
        batch.add_column(sa.Column("billing_period", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True))
        batch.add_column(sa.Column("subscription_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("checkout_url", sa.String(length=500), nullable=True))
        batch.create_foreign_key(
            "fk_payment_intent_subscription",
            "tenant_subscriptions",
            ["subscription_id"],
            ["id"],
        )

    with op.batch_alter_table("credit_transactions") as batch:
        batch.add_column(sa.Column("receipt_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_credit_tx_receipt", "billing_receipts", ["receipt_id"], ["id"])

    if _is_pg():
        for table in RLS_TABLES:
            _enable_rls(table)


def downgrade() -> None:
    if _is_pg():
        for table in RLS_TABLES:
            _disable_rls(table)

    with op.batch_alter_table("credit_transactions") as batch:
        batch.drop_constraint("fk_credit_tx_receipt", type_="foreignkey")
        batch.drop_column("receipt_id")

    with op.batch_alter_table("payment_intents") as batch:
        batch.drop_constraint("fk_payment_intent_subscription", type_="foreignkey")
        batch.drop_column("checkout_url")
        batch.drop_column("subscription_id")
        batch.drop_column("discount_percent")
        batch.drop_column("billing_period")

    with op.batch_alter_table("tenant_credit_accounts") as batch:
        batch.drop_constraint("fk_credit_account_default_pm", type_="foreignkey")
        batch.drop_column("metered_block_reason")
        batch.drop_column("metered_blocked_at")
        batch.drop_column("auto_reload_last_error")
        batch.drop_column("auto_reload_next_attempt_at")
        batch.drop_column("auto_reload_failure_count")
        batch.drop_column("auto_reload_in_flight_charge_id")
        batch.drop_column("default_payment_method_id")

    with op.batch_alter_table("tenant_subscriptions") as batch:
        batch.drop_column("next_renewal_attempt_at")
        batch.drop_column("renewal_attempt_count")
        batch.drop_column("past_due_since")
        batch.drop_column("current_period_end")
        batch.drop_column("discount_percent")
        batch.drop_column("period_fee")
        batch.drop_column("billing_period")

    op.drop_index("ix_receipt_tenant_issued", table_name="billing_receipts")
    op.drop_index(op.f("ix_billing_receipts_tenant_id"), table_name="billing_receipts")
    op.drop_table("billing_receipts")
    op.drop_index(op.f("ix_payment_charges_tenant_id"), table_name="payment_charges")
    op.drop_index("ix_payment_charge_tenant_status", table_name="payment_charges")
    op.drop_table("payment_charges")
    op.drop_index(op.f("ix_tenant_payment_methods_tenant_id"), table_name="tenant_payment_methods")
    op.drop_index("ix_payment_method_tenant_status", table_name="tenant_payment_methods")
    op.drop_table("tenant_payment_methods")
    op.drop_index(
        op.f("ix_tenant_billing_profiles_tenant_id"), table_name="tenant_billing_profiles"
    )
    op.drop_table("tenant_billing_profiles")
    op.drop_table("payment_webhook_events")
    op.drop_table("billing_receipt_sequences")
