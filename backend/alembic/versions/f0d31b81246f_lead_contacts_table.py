"""lead_contacts_table

Fase 40 -- multi-contact per lead/deal dengan peran (Decision Maker,
Champion, dst.), terinspirasi pola `DealContact` di CRM open-source
trycompai/crm. Tabel junction baru `lead_contacts(lead_id, contact_id,
role)` -- terpisah dari `contacts` (PIC company secara umum) karena satu
company bisa punya banyak kontak, dan yang relevan/perannya untuk lead
tertentu bisa beda-beda. RLS ditambahkan langsung di migrasi yang sama
(pola sama `f6a7b8c9d0e1_overtime_requests_table.py`).

Revision ID: f0d31b81246f
Revises: 917a1217f0e6
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0d31b81246f"
down_revision: str | None = "917a1217f0e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "lead_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", "contact_id", name="uq_lead_contact"),
    )
    op.create_index(
        op.f("ix_lead_contacts_tenant_id"), "lead_contacts", ["tenant_id"], unique=False
    )
    op.create_index(op.f("ix_lead_contacts_lead_id"), "lead_contacts", ["lead_id"], unique=False)
    op.create_index(
        op.f("ix_lead_contacts_contact_id"), "lead_contacts", ["contact_id"], unique=False
    )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE lead_contacts ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE lead_contacts FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON lead_contacts
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON lead_contacts"))
        op.execute(sa.text("ALTER TABLE lead_contacts NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE lead_contacts DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_lead_contacts_contact_id"), table_name="lead_contacts")
    op.drop_index(op.f("ix_lead_contacts_lead_id"), table_name="lead_contacts")
    op.drop_index(op.f("ix_lead_contacts_tenant_id"), table_name="lead_contacts")
    op.drop_table("lead_contacts")
