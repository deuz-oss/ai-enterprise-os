"""suppressed_contacts_table

Fase 45 -- company/contact yang ditandai "jangan hubungi lagi" (opt-out,
sudah jadi klien kompetitor, komplain, dst.), terinspirasi
`SuppressedDomain`/`SuppressedContact` di CRM open-source trycompai/crm.
Menunjuk salah satu dari `company_id` atau `contact_id` (XOR, divalidasi
di service layer). RLS ditambahkan langsung di migrasi yang sama (pola
sama `f6a7b8c9d0e1_overtime_requests_table.py`).

Revision ID: fe77e86201de
Revises: 69685a8996cc
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe77e86201de"
down_revision: str | None = "69685a8996cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "suppressed_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_suppressed_contacts_tenant_id"), "suppressed_contacts", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_suppressed_contacts_company_id"),
        "suppressed_contacts",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_suppressed_contacts_contact_id"),
        "suppressed_contacts",
        ["contact_id"],
        unique=False,
    )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE suppressed_contacts ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE suppressed_contacts FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON suppressed_contacts
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON suppressed_contacts"))
        op.execute(sa.text("ALTER TABLE suppressed_contacts NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE suppressed_contacts DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_suppressed_contacts_contact_id"), table_name="suppressed_contacts")
    op.drop_index(op.f("ix_suppressed_contacts_company_id"), table_name="suppressed_contacts")
    op.drop_index(op.f("ix_suppressed_contacts_tenant_id"), table_name="suppressed_contacts")
    op.drop_table("suppressed_contacts")
