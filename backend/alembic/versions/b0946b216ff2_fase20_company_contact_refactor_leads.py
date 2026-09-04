"""Fase 20 item 1: tabel companies/contacts + refactor leads.company_name
(field bebas) -> leads.company_id (FK ke companies). Satu company sekarang
bisa punya banyak contact (procurement/HR/trade marketing, dst.) alih-alih
satu PIC tunggal tertanam di Lead.

Backfill: tiap lead lama dibuatkan satu Company (dari company_name/industry)
+ satu Contact utama (dari contact_name/phone/email, kalau ada salah satu
terisi) sebelum leads.company_id di-set NOT NULL dan kolom lama dihapus.

Revision ID: b0946b216ff2
Revises: a2a07c66c761
Create Date: 2026-09-04 01:30:20.915653
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "b0946b216ff2"
down_revision: str | None = "a2a07c66c761"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_tenant_id"), "companies", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contacts_tenant_id"), "contacts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_contacts_company_id"), "contacts", ["company_id"], unique=False)

    # company_id nullable dulu -- baris lead existing belum punya nilai
    # sampai backfill di bawah selesai.
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("company_id", sa.Uuid(), nullable=True))

    conn = op.get_bind()
    lead_rows = conn.execute(
        sa.text(
            "SELECT id, tenant_id, company_name, industry, contact_name, "
            "contact_phone, contact_email FROM leads"
        )
    ).fetchall()
    now = datetime.now(UTC)
    for (
        lead_id,
        tenant_id,
        company_name,
        industry,
        contact_name,
        contact_phone,
        contact_email,
    ) in lead_rows:
        company_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO companies (id, tenant_id, name, industry, size, source, "
                "created_at, updated_at) "
                "VALUES (:id, :tenant_id, :name, :industry, NULL, 'manual', :now, :now)"
            ).bindparams(
                id=company_id,
                tenant_id=tenant_id,
                name=company_name or "(tanpa nama)",
                industry=industry,
                now=now,
            )
        )
        if contact_name or contact_phone or contact_email:
            conn.execute(
                sa.text(
                    "INSERT INTO contacts (id, tenant_id, company_id, name, department, "
                    "email, phone, linkedin_url, is_primary, created_at) "
                    "VALUES (:id, :tenant_id, :company_id, :name, NULL, :email, :phone, "
                    "NULL, :is_primary, :now)"
                ).bindparams(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    company_id=company_id,
                    name=contact_name or company_name or "(tanpa nama)",
                    email=contact_email,
                    phone=contact_phone,
                    is_primary=True,
                    now=now,
                )
            )
        conn.execute(
            sa.text("UPDATE leads SET company_id = :company_id WHERE id = :lead_id").bindparams(
                company_id=company_id, lead_id=lead_id
            )
        )

    # Index lama nempel di kolom company_name -- harus di-drop DULU (di luar
    # batch di bawah), karena batch_alter_table mereflect skema tabel apa
    # adanya lalu coba re-create SEMUA index yang masih terdaftar; kalau
    # company_name sudah didrop dalam batch yang sama tapi index-nya belum,
    # recreate itu gagal "no such column: company_name" (ditemukan lewat
    # test_migrations.py, bukan dugaan).
    op.drop_index("ix_leads_company_name", table_name="leads")

    with op.batch_alter_table("leads") as batch:
        batch.alter_column("company_id", nullable=False)
        batch.create_foreign_key("fk_leads_company_id", "companies", ["company_id"], ["id"])
        batch.drop_column("company_name")
        batch.drop_column("industry")
        batch.drop_column("contact_name")
        batch.drop_column("contact_phone")
        batch.drop_column("contact_email")
    op.create_index("ix_leads_company_id", "leads", ["company_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("company_name", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("industry", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("contact_name", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("contact_phone", sa.String(length=60), nullable=True))
        batch.add_column(sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.create_index("ix_leads_company_name", "leads", ["company_name"], unique=False)

    conn = op.get_bind()
    lead_rows = conn.execute(
        sa.text(
            "SELECT l.id, c.name, c.industry, c.id FROM leads l "
            "JOIN companies c ON l.company_id = c.id"
        )
    ).fetchall()
    for lead_id, company_name, industry, company_id in lead_rows:
        primary = conn.execute(
            sa.text(
                "SELECT name, phone, email FROM contacts WHERE company_id = :company_id "
                "ORDER BY is_primary DESC, created_at ASC LIMIT 1"
            ).bindparams(company_id=company_id)
        ).fetchone()
        conn.execute(
            sa.text(
                "UPDATE leads SET company_name = :company_name, industry = :industry, "
                "contact_name = :contact_name, contact_phone = :contact_phone, "
                "contact_email = :contact_email WHERE id = :lead_id"
            ).bindparams(
                company_name=company_name,
                industry=industry,
                contact_name=primary[0] if primary else None,
                contact_phone=primary[1] if primary else None,
                contact_email=primary[2] if primary else None,
                lead_id=lead_id,
            )
        )

    # Sama seperti catatan di upgrade(): index harus di-drop SEBELUM batch
    # yang men-drop kolomnya, bukan sesudah.
    op.drop_index("ix_leads_company_id", table_name="leads")
    with op.batch_alter_table("leads") as batch:
        batch.drop_constraint("fk_leads_company_id", type_="foreignkey")
        batch.drop_column("company_id")
    op.drop_table("contacts")
    op.drop_table("companies")
