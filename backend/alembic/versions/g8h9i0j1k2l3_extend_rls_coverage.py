"""Perluas RLS ke semua tabel bisnis ber-tenant_id NOT NULL yang lahir
setelah migrasi RLS awal (03c4cecd231b)

Temuan audit (2026-09-02): 34 tabel ber-`tenant_id` yang dibuat setelah
migrasi RLS awal TIDAK pernah ditambahkan ke `03c4cecd231b`'s
`BUSINESS_TABLES` -- isolasinya bergantung sepenuhnya pada filter ORM di
`core/tenancy.py::do_orm_execute`, yang fail-open (`tenant_id is None` ->
query tanpa scope) dan cuma berlaku untuk SELECT via ORM (bukan bulk
update/delete via `session.execute()` mentah).

Dari 34 tabel: `users`/`audit_logs` tetap dikecualikan (nullable tenant_id,
pola sama seperti keputusan di `03c4cecd231b`). `ai_interview_responses`
dan `payroll_run_tokens` JUGA dikecualikan -- keduanya di-query lewat token
publik SEBELUM `set_tenant()` dipanggil (`_resolve_response_by_token()`,
`client_view()`/`decide_by_token()`) sehingga RLS akan mem-block lookup
awal itu sendiri (isolasinya sudah benar via `execution_options(
include_with_loader_criteria=False)` + `set_tenant()` manual segera setelah
baris ditemukan -- pola yang sama persis dipakai `job_portal` untuk
`placements`, yang MEMANG sudah RLS-covered sejak `03c4cecd231b` -- lihat
catatan penting di bawah).

CATATAN PENTING ditemukan saat audit ini: `placements` sudah RLS-covered
sejak migrasi awal, TAPI `job_portal/service.py::_resolve_placement_by_token`
melakukan pola lookup-sebelum-set_tenant yang SAMA seperti
`ai_interview_responses`/`payroll_run_tokens` di atas. ARTINYA endpoint
`GET /public/applications/{token}` kemungkinan sudah lama gagal (404 keliru)
di Postgres dengan RLS yang benar-benar aktif -- gap ini baru mungkin
kentara sekarang karena migrasi ini adalah migrasi PERTAMA yang membuat RLS
benar-benar berlaku (lihat perbaikan role `aeos_app` di docker-compose.yml,
sebelumnya app connect sebagai superuser `postgres` yang SELALU melewati
RLS apa pun kebijakannya). Perbaikan `placements`/`_resolve_placement_by_token`
TIDAK termasuk migrasi ini -- dicatat sebagai temuan terpisah yang perlu
diselesaikan segera sesudah ini (lihat plan file).

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-09-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g8h9i0j1k2l3"
down_revision: str | None = "f7g8h9i0j1k2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Semua tabel ber-tenant_id NOT NULL yang lahir setelah 03c4cecd231b, MINUS
# ai_interview_responses & payroll_run_tokens (lihat docstring -- pre-tenant
# token lookup, isolasi ORM manual sudah benar, RLS akan mem-block dirinya
# sendiri kalau ditambah di sini tanpa perbaikan lookup-nya dulu).
NEW_BUSINESS_TABLES = [
    "accounting_periods",
    "accounts",
    "ai_interview_templates",
    "ai_usage_events",
    "attendance_corrections",
    "attendance_records",
    "bank_statement_lines",
    "bank_transactions",
    "blacklist_entries",
    "chat_channel_members",
    "chat_channels",
    "chat_message_reactions",
    "chat_messages",
    "cv_intakes",
    "employee_insurances",
    "fixed_assets",
    "interview_schedules",
    "journal_rules",
    "leave_balances",
    "leave_requests",
    "notifications",
    "notion_pages",
    "payment_requests",
    "payslip_components",
    "pr_approval_steps",
    "pr_approvals",
    "purchase_bills",
    "standard_cv_versions",
    "tenant_app_licenses",
    "tenant_cv_branding",
]

# Tabel yang SUDAH RLS-covered sejak 03c4cecd231b -- di-FORCE di migrasi ini
# supaya berlaku juga untuk role pemilik tabel, bukan cuma grantee biasa
# (defense-in-depth: benar SELAMA pemilik tetap `postgres` seperti sekarang,
# tapi tidak bergantung pada asumsi ownership itu tidak pernah berubah).
EXISTING_BUSINESS_TABLES = [
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
    # Defensive: kegagalan pembuatan policy tidak boleh menggagalkan migrasi
    # (pola sama persis 03c4cecd231b).
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


def _force_only(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


def _disable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))


def upgrade() -> None:
    if not _is_pg():
        return
    for table in NEW_BUSINESS_TABLES:
        _enable_rls(table)
    for table in EXISTING_BUSINESS_TABLES:
        _force_only(table)


def downgrade() -> None:
    if not _is_pg():
        return
    for table in EXISTING_BUSINESS_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
    for table in NEW_BUSINESS_TABLES:
        _disable_rls(table)
