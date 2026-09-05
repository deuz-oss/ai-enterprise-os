"""Perluas RLS ke tabel ber-tenant_id NOT NULL yang lahir setelah migrasi
RLS terakhir (g8h9i0j1k2l3) dan sebelum Fase 28 -- ditemukan lewat audit
`test_rls_coverage.py` saat mengerjakan Fase 28 (2026-09-05): 14 tabel dari
sprint Fase 20-27 (Quotation/Agreement/CRM, Referral, HRD Movement/Vaccine/
Warning Letter) tidak pernah ditambahkan ke daftar RLS, isolasinya diam-diam
cuma bergantung pada filter ORM otomatis (fail-open, tidak berlaku untuk
bulk update/delete via `session.execute()` mentah) -- pola bug yang sama
persis dengan yang diperbaiki `g8h9i0j1k2l3`.

Sudah dicek: tidak ada satu pun dari 14 tabel ini yang diquery lewat token
publik sebelum `set_tenant()` dipanggil (beda dari `payroll_run_tokens`/
`ai_interview_responses`/`payment_intents`), jadi aman langsung di-FORCE
tanpa pengecualian.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-05 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_BUSINESS_TABLES = [
    "agreement_templates",
    "agreements",
    "candidate_experiences",
    "companies",
    "contacts",
    "employee_movements",
    "employment_contract_templates",
    "job_order_templates",
    "quotation_templates",
    "quotations",
    "referral_program_settings",
    "referral_rewards",
    "vaccine_records",
    "warning_letters",
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
    if not _is_pg():
        return
    for table in NEW_BUSINESS_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    if not _is_pg():
        return
    for table in NEW_BUSINESS_TABLES:
        _disable_rls(table)
