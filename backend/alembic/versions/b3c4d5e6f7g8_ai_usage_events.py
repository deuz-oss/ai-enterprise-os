"""ai_usage_events: pencatatan token/biaya AI per tenant (dasar tagihan AI Add-on)

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-01 00:00:00.000000

Sengaja TIDAK masuk daftar RLS `BUSINESS_TABLES` di migrasi `03c4cecd231b`
-- tabel itu sudah lama tidak diperbarui, tabel bisnis baru sesudahnya
(`interview_schedules`, `employee_insurances`, dst di `s3t0u1v2w3x4`) juga
tidak ditambahkan ke RLS Postgres, cukup mengandalkan filter tenant
otomatis level-ORM (`core/tenancy.py::do_orm_execute`) yang berlaku
universal terlepas dari RLS -- diikuti presedennya di sini.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7g8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("call_type", sa.String(length=20), nullable=False),
        sa.Column("feature", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_idr", sa.Numeric(14, 4), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_usage_events_tenant_id"), "ai_usage_events", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_ai_usage_events_user_id"), "ai_usage_events", ["user_id"], unique=False
    )
    op.create_index(
        "ix_ai_usage_tenant_created", "ai_usage_events", ["tenant_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_ai_usage_tenant_feature_created",
        "ai_usage_events",
        ["tenant_id", "feature", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_tenant_feature_created", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_tenant_created", table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_user_id"), table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_tenant_id"), table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
