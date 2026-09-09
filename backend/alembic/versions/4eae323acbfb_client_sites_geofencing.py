"""client_sites_geofencing

Tabel baru `client_sites` -- titik lokasi kantor/cabang klien untuk
geofencing absensi (Fase 34). Satu Client bisa punya banyak site (radius
beda-beda per cabang); `employees.site_id` (kolom baru, nullable) menaut
karyawan ke site kerjanya -- kosong = absen bebas (perilaku lama, tidak
berubah), terisi = wajib dalam radius site itu saat clock-in/out (lihat
`ess/service.py::mobile_clock`/`_enforce_site_radius`).

RLS ditambahkan LANGSUNG di migrasi yang sama dengan pembuatan tabel
(pola konsisten sejak `9349e6c0fcac_offering_settings_table.py`).

Revision ID: 4eae323acbfb
Revises: a7b8c9d0e1f2
Create Date: 2026-09-07 23:08:18.137354

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4eae323acbfb"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "client_sites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("radius_meters", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_sites_client_id"), "client_sites", ["client_id"], unique=False)
    op.create_index(op.f("ix_client_sites_tenant_id"), "client_sites", ["tenant_id"], unique=False)

    # Batch mode agar ALTER ber-constraint juga jalan di SQLite (pola sama
    # `a7f2d94c1e58_kolom_user_id_karyawan_portal_selfservice.py`).
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("site_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_employees_site_id_client_sites", "client_sites", ["site_id"], ["id"]
        )
        batch_op.create_index(op.f("ix_employees_site_id"), ["site_id"], unique=False)

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE client_sites ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE client_sites FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON client_sites
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON client_sites"))
        op.execute(sa.text("ALTER TABLE client_sites NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE client_sites DISABLE ROW LEVEL SECURITY"))
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_index(op.f("ix_employees_site_id"))
        batch_op.drop_constraint("fk_employees_site_id_client_sites", type_="foreignkey")
        batch_op.drop_column("site_id")
    op.drop_index(op.f("ix_client_sites_tenant_id"), table_name="client_sites")
    op.drop_index(op.f("ix_client_sites_client_id"), table_name="client_sites")
    op.drop_table("client_sites")
