"""tabel tenant_app_licenses + seed paket penuh tenant lama (Fase 7)

Revision ID: a1b2c3d4e5f6
Revises: f9c2e6b8d314
Create Date: 2026-08-25 05:30:00.000000

"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f9c2e6b8d314"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.apps import APP_REGISTRY

    op.create_table(
        "tenant_app_licenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("app_key", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.Enum("trial", "aktif", "kedaluwarsa", name="licensestatus", native_enum=False, length=50),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "app_key", name="uq_license_tenant_app"),
    )
    op.create_index(
        op.f("ix_tenant_app_licenses_tenant_id"),
        "tenant_app_licenses",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_app_licenses_app_key"),
        "tenant_app_licenses",
        ["app_key"],
        unique=False,
    )

    # Tenant yang sudah berjalan mendapat paket penuh (grandfathered):
    # penjualan granular dilakukan dengan mencabut lisensi, bukan menutup akses.
    conn = op.get_bind()
    tenant_rows = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    stamp = "2026-08-25 00:00:00"
    for (tenant_id,) in tenant_rows:
        for key in APP_REGISTRY:
            conn.execute(
                sa.text(
                    "INSERT INTO tenant_app_licenses "
                    "(id, tenant_id, app_key, status, started_at, expires_at) "
                    "VALUES (:id, :tenant_id, :app_key, 'aktif', :started_at, NULL)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(tenant_id),
                    "app_key": key,
                    "started_at": stamp,
                },
            )


def downgrade() -> None:
    op.drop_table("tenant_app_licenses")
