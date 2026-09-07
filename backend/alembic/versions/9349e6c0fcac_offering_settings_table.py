"""offering_settings_table

Konfigurasi per-tenant untuk email surat penawaran ke kandidat (gap
ditemukan 2026-09-07 lewat perbandingan alur MYOHRIS: sebelumnya TIDAK ADA
email sungguhan yang dikirim ke kandidat sama sekali -- lihat docstring
`OfferingSettings` di recruitment/models.py).

RLS ditambahkan LANGSUNG di migrasi yang sama dengan pembuatan tabel (pola
`_enable_rls` dari `g8h9i0j1k2l3_extend_rls_coverage.py`) -- bukan
ditunda ke migrasi "extend coverage" berikutnya seperti kebiasaan lama,
supaya tabel baru tidak pernah lolos tanpa RLS sejak awal.

Revision ID: 9349e6c0fcac
Revises: ba192dfbcc82
Create Date: 2026-09-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9349e6c0fcac"
down_revision: str | None = "ba192dfbcc82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "offering_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("return_emails", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_offering_settings_tenant_id"), "offering_settings", ["tenant_id"], unique=False
    )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE offering_settings ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE offering_settings FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON offering_settings
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON offering_settings"))
        op.execute(sa.text("ALTER TABLE offering_settings NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE offering_settings DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_offering_settings_tenant_id"), table_name="offering_settings")
    op.drop_table("offering_settings")
