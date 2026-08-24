"""password_reset_tokens + RLS postgres

Revision ID: 03c4cecd231b
Revises: 216c6e7b9907
Create Date: 2026-08-24 12:08:05.832673

Tabel token reset password bersifat lintas modul; ditambah pula kebijakan
Row Level Security PostgreSQL sebagai lapisan kedua isolasi multi-tenant
(di luar filter ORM). RLS hanya diterapkan pada 20 tabel bisnis ber-
tenant_id NOT NULL — tabel users/audit_logs/token sengaja dikecualikan
karena memuat baris tanpa tenant (akun platform, event pra-login).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "03c4cecd231b"
down_revision: str | None = "216c6e7b9907"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabel bisnis TenantMixin (tenant_id selalu ada & NOT NULL).
BUSINESS_TABLES = [
    "ai_document_chunks",
    "ai_screenings",
    "attendance_summaries",
    "candidates",
    "cash_flow_entries",
    "clients",
    "employee_documents",
    "employees",
    "employment_contracts",
    "esign_requests",
    "invoices",
    "job_orders",
    "journal_entries",
    "journal_lines",
    "lead_activities",
    "leads",
    "legal_documents",
    "payroll_runs",
    "payslips",
    "placements",
]


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable_rls(table: str) -> None:
    # Defensive: kegagalan pembuatan policy tidak boleh menggagalkan migrasi.
    op.execute(
        sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    )
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
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )

    if _is_pg():
        for table in BUSINESS_TABLES:
            _enable_rls(table)


def downgrade() -> None:
    if _is_pg():
        for table in reversed(BUSINESS_TABLES):
            _disable_rls(table)
    op.drop_index(
        op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
