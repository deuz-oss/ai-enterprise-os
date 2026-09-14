"""emergency_contacts_one_to_many

Kontak darurat karyawan bisa lebih dari satu -- 3 kolom flat
`employees.emergency_contact_name/relation/phone` (satu kontak saja)
diganti tabel `employee_emergency_contacts` (one-to-many, pola sama
`employee_insurances`).

Data lama TIDAK dibuang: setiap employee yang sudah punya
`emergency_contact_name` terisi di-backfill jadi satu baris kontak
(`is_primary=1`) sebelum kolom lamanya dihapus.

Batch mode (pola sama migrasi Fase 36/Tier-1 sebelumnya) supaya ALTER
TABLE juga jalan di SQLite.

Revision ID: 9a1c2e3f4b5d
Revises: 7fffe60cc637
Create Date: 2026-09-14 18:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a1c2e3f4b5d"
down_revision: str | None = "7fffe60cc637"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_emergency_contacts",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column(
            "tenant_id", sa.CHAR(32), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "employee_id", sa.CHAR(32), sa.ForeignKey("employees.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("relation", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # Backfill: satu baris per employee yang sudah punya kontak lama terisi.
    op.execute(
        """
        INSERT INTO employee_emergency_contacts
            (id, tenant_id, employee_id, name, relation, phone, is_primary, created_at)
        SELECT
            lower(hex(randomblob(16))), tenant_id, id,
            emergency_contact_name, emergency_contact_relation, emergency_contact_phone,
            1, CURRENT_TIMESTAMP
        FROM employees
        WHERE emergency_contact_name IS NOT NULL AND emergency_contact_name != ''
        """
    )

    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("emergency_contact_name")
        batch_op.drop_column("emergency_contact_relation")
        batch_op.drop_column("emergency_contact_phone")


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(
            sa.Column("emergency_contact_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("emergency_contact_relation", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("emergency_contact_phone", sa.String(length=60), nullable=True)
        )

    # Backfill terbalik: ambil kontak utama (atau kontak pertama) per employee.
    op.execute(
        """
        UPDATE employees
        SET
            emergency_contact_name = (
                SELECT c.name FROM employee_emergency_contacts c
                WHERE c.employee_id = employees.id
                ORDER BY c.is_primary DESC, c.created_at ASC LIMIT 1
            ),
            emergency_contact_relation = (
                SELECT c.relation FROM employee_emergency_contacts c
                WHERE c.employee_id = employees.id
                ORDER BY c.is_primary DESC, c.created_at ASC LIMIT 1
            ),
            emergency_contact_phone = (
                SELECT c.phone FROM employee_emergency_contacts c
                WHERE c.employee_id = employees.id
                ORDER BY c.is_primary DESC, c.created_at ASC LIMIT 1
            )
        WHERE EXISTS (
            SELECT 1 FROM employee_emergency_contacts c WHERE c.employee_id = employees.id
        )
        """
    )
    op.drop_table("employee_emergency_contacts")
