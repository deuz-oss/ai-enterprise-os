"""multi-tenant: tabel tenants + kolom tenant_id di semua tabel bisnis

Aman untuk database yang sudah berisi data:
1. Buat tabel `tenants`.
2. Tambahkan kolom `tenant_id` sebagai nullable di semua tabel bisnis (+users).
3. Backfill: sisipkan tenant "default" lalu isi semua baris lama dengannya.
4. Perketat menjadi NOT NULL (kecuali users) + unik komposit per tenant.

Semua perubahan struktural memakai batch_alter_table agar kompatibel SQLite.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e1e18040be"
down_revision: str | None = "d1ce2c59c7da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ID deterministik untuk tenant default hasil backfill.
DEFAULT_TENANT_ID = "0a000000-0000-4000-8000-000000000001"

# Tabel bisnis dengan tenant_id NOT NULL (semua model TenantMixin).
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


def upgrade() -> None:
    # 1) Tabel induk
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", name="tenantstatus", native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # 2) Kolom nullable dulu agar aman untuk tabel berisi baris
    for table in BUSINESS_TABLES + ["users"]:
        op.add_column(table, sa.Column("tenant_id", sa.Uuid(), nullable=True))

    # 3) Backfill ke tenant default
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, status, created_at) "
            "VALUES (:id, 'Default', 'default', 'aktif', CURRENT_TIMESTAMP)"
        ).bindparams(id=DEFAULT_TENANT_ID)
    )
    for table in BUSINESS_TABLES + ["users"]:
        op.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL").bindparams(
                tid=DEFAULT_TENANT_ID
            )
        )

    # 4) Unik komposit menggantikan unik global (indeks unik lama dihapus duluan)
    op.drop_index(op.f("ix_employees_employee_no"), table_name="employees")
    op.drop_index(op.f("ix_invoices_invoice_no"), table_name="invoices")
    op.drop_index(op.f("ix_users_email"), table_name="users")

    # 5) Perketat NOT NULL + FK + indeks, per tabel (batch untuk SQLite)
    for table in BUSINESS_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("tenant_id", existing_type=sa.Uuid(), nullable=False)
            batch.create_foreign_key(f"fk_{table}_tenant_id", "tenants", ["tenant_id"], ["id"])
        op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"], unique=False)

    with op.batch_alter_table("employees") as batch:
        batch.create_index(op.f("ix_employees_employee_no"), ["employee_no"], unique=False)
        batch.create_unique_constraint("uq_employee_tenant_no", ["tenant_id", "employee_no"])

    with op.batch_alter_table("invoices") as batch:
        batch.create_index(op.f("ix_invoices_invoice_no"), ["invoice_no"], unique=False)
        batch.create_unique_constraint("uq_invoice_tenant_no", ["tenant_id", "invoice_no"])

    with op.batch_alter_table("users") as batch:
        # tetap nullable: platform_admin tidak terikat tenant
        batch.create_foreign_key("fk_users_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch.create_unique_constraint("uq_user_tenant_email", ["tenant_id", "email"])
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def downgrade() -> None:
    sqlite = _is_sqlite()

    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    with op.batch_alter_table("users") as batch:
        if not sqlite:
            batch.drop_constraint("uq_user_tenant_email", type_="unique")
            batch.drop_constraint("fk_users_tenant_id", type_="foreignkey")
        batch.alter_column("tenant_id", existing_type=sa.Uuid(), nullable=True)
        batch.drop_column("tenant_id")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    for table in reversed(BUSINESS_TABLES):
        # Hapus indeks kolom SEBELUM kolomnya dijatuhkan; batch merefleksikan
        # indeks lama saat membangun ulang tabel dan akan gagal bila masih ada.
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        with op.batch_alter_table(table) as batch:
            if not sqlite:
                # Di SQLite constraint tidak terefleksi bernama; ia hilang
                # bersama kolom yang dijatuhkan.
                batch.drop_constraint(f"fk_{table}_tenant_id", type_="foreignkey")
            batch.alter_column("tenant_id", existing_type=sa.Uuid(), nullable=True)
            batch.drop_column("tenant_id")

    with op.batch_alter_table("invoices") as batch:
        if not sqlite:
            batch.drop_constraint("uq_invoice_tenant_no", type_="unique")
    # indeks non-unik masih ada dari upgrade → ganti ke unik
    op.drop_index(op.f("ix_invoices_invoice_no"), table_name="invoices")
    op.create_index(op.f("ix_invoices_invoice_no"), "invoices", ["invoice_no"], unique=True)

    with op.batch_alter_table("employees") as batch:
        if not sqlite:
            batch.drop_constraint("uq_employee_tenant_no", type_="unique")
    op.drop_index(op.f("ix_employees_employee_no"), table_name="employees")
    op.create_index(op.f("ix_employees_employee_no"), "employees", ["employee_no"], unique=True)

    op.drop_table("tenants")
