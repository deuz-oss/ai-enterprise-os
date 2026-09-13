"""google_mailbox_sync

Fase 47 -- sync Gmail/Google Calendar ke Activity lead, per-user (koneksi
akun Google milik staf sendiri via OAuth, bukan tenant-wide). Tabel baru
`google_mailbox_connections` + 2 kolom dedup di `lead_activities` supaya
sync berulang tidak menduplikasi entri yang sudah pernah diimpor.

Batch mode untuk `lead_activities` (pola sama
`bd33f16a67b6_shift_and_address_fields.py`) supaya ALTER TABLE juga jalan
di SQLite. RLS untuk tabel baru ditambahkan langsung di migrasi yang sama
(pola sama `f6a7b8c9d0e1_overtime_requests_table.py`).

Revision ID: a921d29e0036
Revises: ca3907dde94f
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a921d29e0036"
down_revision: str | None = "ca3907dde94f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "google_mailbox_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("google_email", sa.String(length=255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_google_mailbox_user"),
    )
    op.create_index(
        op.f("ix_google_mailbox_connections_tenant_id"),
        "google_mailbox_connections",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_google_mailbox_connections_user_id"),
        "google_mailbox_connections",
        ["user_id"],
        unique=False,
    )

    with op.batch_alter_table("lead_activities") as batch:
        batch.add_column(sa.Column("external_source", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("external_id", sa.String(length=255), nullable=True))
        batch.create_index(op.f("ix_lead_activities_external_id"), ["external_id"], unique=False)
        batch.create_unique_constraint(
            "uq_lead_activity_external", ["tenant_id", "external_source", "external_id"]
        )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE google_mailbox_connections ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE google_mailbox_connections FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON google_mailbox_connections
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("lead_activities") as batch:
        batch.drop_constraint("uq_lead_activity_external", type_="unique")
        batch.drop_index(op.f("ix_lead_activities_external_id"))
        batch.drop_column("external_id")
        batch.drop_column("external_source")

    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON google_mailbox_connections"))
        op.execute(sa.text("ALTER TABLE google_mailbox_connections NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE google_mailbox_connections DISABLE ROW LEVEL SECURITY"))
    op.drop_index(
        op.f("ix_google_mailbox_connections_user_id"), table_name="google_mailbox_connections"
    )
    op.drop_index(
        op.f("ix_google_mailbox_connections_tenant_id"), table_name="google_mailbox_connections"
    )
    op.drop_table("google_mailbox_connections")
