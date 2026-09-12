"""custom_fields_tables

Fase 41 -- field tambahan admin-configurable per entitas CRM
(Company/Contact/Lead), terinspirasi `FieldDefinition`/`FieldValue` di
CRM open-source trycompai/crm. Tiga tabel baru:

- `custom_field_definitions`: skema field (entity, key, label, tipe,
  wajib/tidak, urutan).
- `custom_field_options`: daftar opsi untuk field bertipe `select`.
- `custom_field_values`: nilai per record -- `entity_id` sengaja
  polimorfik tanpa FK DB (satu tabel value melayani 3 jenis entitas
  sekaligus), validasi keberadaan record dilakukan di service layer.

RLS ditambahkan langsung di migrasi yang sama (pola sama
`f6a7b8c9d0e1_overtime_requests_table.py`).

Revision ID: b89a4b594ad5
Revises: f0d31b81246f
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b89a4b594ad5"
down_revision: str | None = "f0d31b81246f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("custom_field_definitions", "custom_field_options", "custom_field_values")


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity",
            sa.Enum("company", "contact", "lead", name="fieldentity", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column(
            "field_type",
            sa.Enum(
                "text",
                "long_text",
                "number",
                "date",
                "checkbox",
                "select",
                "url",
                "email",
                "phone",
                name="fieldtype",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "entity", "key", name="uq_custom_field_tenant_entity_key"),
    )
    op.create_index(
        op.f("ix_custom_field_definitions_entity"),
        "custom_field_definitions",
        ["entity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_definitions_tenant_id"),
        "custom_field_definitions",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "custom_field_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("field_definition_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["field_definition_id"], ["custom_field_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_custom_field_options_field_definition_id"),
        "custom_field_options",
        ["field_definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_options_tenant_id"),
        "custom_field_options",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "custom_field_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("field_definition_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["field_definition_id"], ["custom_field_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "field_definition_id", "entity_id", name="uq_custom_field_value_definition_entity"
        ),
    )
    op.create_index(
        op.f("ix_custom_field_values_field_definition_id"),
        "custom_field_values",
        ["field_definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custom_field_values_entity_id"), "custom_field_values", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_custom_field_values_tenant_id"), "custom_field_values", ["tenant_id"], unique=False
    )

    if not _is_pg():
        return
    for table in _TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id::text = current_setting('app.current_tenant', true))
                WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
                """
            )
        )


def downgrade() -> None:
    if _is_pg():
        for table in _TABLES:
            op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
            op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    op.drop_index(op.f("ix_custom_field_values_tenant_id"), table_name="custom_field_values")
    op.drop_index(op.f("ix_custom_field_values_entity_id"), table_name="custom_field_values")
    op.drop_index(
        op.f("ix_custom_field_values_field_definition_id"), table_name="custom_field_values"
    )
    op.drop_table("custom_field_values")

    op.drop_index(op.f("ix_custom_field_options_tenant_id"), table_name="custom_field_options")
    op.drop_index(
        op.f("ix_custom_field_options_field_definition_id"), table_name="custom_field_options"
    )
    op.drop_table("custom_field_options")

    op.drop_index(
        op.f("ix_custom_field_definitions_tenant_id"), table_name="custom_field_definitions"
    )
    op.drop_index(op.f("ix_custom_field_definitions_entity"), table_name="custom_field_definitions")
    op.drop_table("custom_field_definitions")
