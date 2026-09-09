"""fix_now_function_default_sqlite

Lima migrasi sebelumnya (`f6a7b8c9d0e1_overtime_requests_table.py`,
`4eae323acbfb_client_sites_geofencing.py`,
`519f65da4618_salary_holds_table.py`,
`a7b8c9d0e1f2_client_portal_access_table.py`,
`b72d2fab40a7_onboarding_invites_documents.py`) memakai
`server_default=sa.text("now()")` untuk kolom timestamp -- literal SQL
mentah yang cuma valid di PostgreSQL (SQLite tidak punya fungsi
`now()`). Ini luput dari test suite karena test membangun skema lewat
`Base.metadata.create_all()` (pakai `func.now()` dialect-aware di level
model), bukan lewat migrasi Alembic sungguhan seperti di `data/aeos.db`.

Baru ketahuan saat "Buat Link Portal" di Client Detail gagal 500
(`sqlite3.OperationalError: unknown function: now()`). File migrasi
sumber sudah diperbaiki ke `sa.func.now()` (dialect-aware, sama pola
semua model ORM), tapi database yang SUDAH di-migrate duluan
(`data/aeos.db`) sudah kadung punya `DEFAULT (now())` yang rusak
tertanam di skemanya -- migrasi ini memperbaiki itu lewat
`batch_alter_table` (pola sama `bd33f16a67b6_shift_and_address_fields.py`)
supaya jalan juga di SQLite.

Revision ID: 2dbfdfcc8679
Revises: bd33f16a67b6
Create Date: 2026-09-09 09:45:01.544913

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2dbfdfcc8679"
down_revision: str | None = "bd33f16a67b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES_COLUMNS = [
    ("client_sites", "created_at"),
    ("salary_holds", "held_at"),
    ("client_portal_access", "created_at"),
    ("onboarding_invites", "created_at"),
    ("onboarding_documents", "uploaded_at"),
    ("overtime_requests", "created_at"),
]


def upgrade() -> None:
    for table, column in _TABLES_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                existing_nullable=False,
            )


def downgrade() -> None:
    for table, column in reversed(_TABLES_COLUMNS):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                existing_nullable=False,
            )
