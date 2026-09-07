"""client_portal_access_table

Tabel baru untuk akses portal monitoring read-only klien (link tanpa akun,
lihat kehadiran & lembur karyawan yang ditempatkan di perusahaan mereka).
BEDA dari `payroll_run_tokens`/`onboarding_invites` -- token di sini
PERSISTEN (satu baris per klien, `uq_client_portal_access_client`), tidak
expired otomatis, dicabut/diganti HR secara eksplisit.

SENGAJA TIDAK ditambahkan RLS policy -- pola sama persis
`payroll_run_tokens`/`onboarding_invites`/`payment_intents` (lihat
`tests/test_rls_coverage.py::EXCLUDED_TABLES`): baris ini dicari lewat
token publik SEBELUM tenant diketahui, RLS akan memblokir lookup awal itu
sendiri. Isolasi tetap benar lewat `set_tenant()` manual segera setelah
baris ditemukan.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-07 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_portal_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", name="uq_client_portal_access_client"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_client_portal_access_client_id"),
        "client_portal_access",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_portal_access_tenant_id"),
        "client_portal_access",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_client_portal_access_tenant_id"), table_name="client_portal_access")
    op.drop_index(op.f("ix_client_portal_access_client_id"), table_name="client_portal_access")
    op.drop_table("client_portal_access")
