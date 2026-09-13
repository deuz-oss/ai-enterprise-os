"""ai_lead_briefs_table

Fase 48 -- ringkasan AI atas lead presales, dirangkum dari data yang
sudah ada di Aeos (bukan riset fakta eksternal -- lihat docstring
`app.modules.ai.models.LeadBrief`). RLS ditambahkan langsung di migrasi
yang sama (pola sama `f6a7b8c9d0e1_overtime_requests_table.py`).

Revision ID: 17ea218b3149
Revises: a921d29e0036
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "17ea218b3149"
down_revision: str | None = "a921d29e0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "ai_lead_briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_lead_briefs_tenant_id"), "ai_lead_briefs", ["tenant_id"], unique=False
    )
    op.create_index(op.f("ix_ai_lead_briefs_lead_id"), "ai_lead_briefs", ["lead_id"], unique=False)

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE ai_lead_briefs ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE ai_lead_briefs FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON ai_lead_briefs
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON ai_lead_briefs"))
        op.execute(sa.text("ALTER TABLE ai_lead_briefs NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE ai_lead_briefs DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_ai_lead_briefs_lead_id"), table_name="ai_lead_briefs")
    op.drop_index(op.f("ix_ai_lead_briefs_tenant_id"), table_name="ai_lead_briefs")
    op.drop_table("ai_lead_briefs")
