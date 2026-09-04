"""Fase 25: tabel employment_contract_templates + employment_contracts.
template_id/field_values -- generator kontrak karyawan, terpisah dari
AgreementTemplate/Agreement (presales) meski pola field_schema+rendering
sama.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-04 16:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employment_contract_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("field_schema", sa.Text(), nullable=False),
        sa.Column("footer_text", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index(
        op.f("ix_employment_contract_templates_tenant_id"),
        "employment_contract_templates",
        ["tenant_id"],
        unique=False,
    )

    with op.batch_alter_table("employment_contracts") as batch:
        batch.add_column(sa.Column("template_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("field_values", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_employment_contracts_template_id",
            "employment_contract_templates",
            ["template_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("employment_contracts") as batch:
        batch.drop_constraint("fk_employment_contracts_template_id", type_="foreignkey")
        batch.drop_column("field_values")
        batch.drop_column("template_id")

    op.drop_index(
        op.f("ix_employment_contract_templates_tenant_id"),
        table_name="employment_contract_templates",
    )
    op.drop_table("employment_contract_templates")
