"""saved_lead_views_table

Fase 44 -- tampilan Pipeline tersimpan (kombinasi filter tahap/pemilik/
pencarian/mode tampilan), opsional dibagikan ke tim, terinspirasi
`SavedView` di CRM open-source trycompai/crm. RLS ditambahkan langsung
di migrasi yang sama (pola sama `f6a7b8c9d0e1_overtime_requests_table.py`).

Revision ID: 69685a8996cc
Revises: c6554afa5ab0
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "69685a8996cc"
down_revision: str | None = "c6554afa5ab0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "saved_lead_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("filters", sa.Text(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_saved_lead_views_tenant_id"), "saved_lead_views", ["tenant_id"], unique=False
    )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE saved_lead_views ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE saved_lead_views FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON saved_lead_views
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON saved_lead_views"))
        op.execute(sa.text("ALTER TABLE saved_lead_views NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE saved_lead_views DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_saved_lead_views_tenant_id"), table_name="saved_lead_views")
    op.drop_table("saved_lead_views")
