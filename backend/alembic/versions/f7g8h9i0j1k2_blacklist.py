"""Black Lists (riset arsitektur MyOHRIS) -- blacklist_entries

Revision ID: f7g8h9i0j1k2
Revises: d5e6f7g8h9i0
Create Date: 2026-09-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7g8h9i0j1k2"
down_revision: str | None = "d5e6f7g8h9i0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blacklist_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="menunggu_review", nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_blacklist_entries_tenant_id"), "blacklist_entries", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_blacklist_entries_candidate_id"),
        "blacklist_entries",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blacklist_entries_status"), "blacklist_entries", ["status"], unique=False
    )
    op.create_index(
        "ix_blacklist_entries_tenant_status",
        "blacklist_entries",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_blacklist_entries_tenant_candidate",
        "blacklist_entries",
        ["tenant_id", "candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    t = "blacklist_entries"
    op.drop_index("ix_blacklist_entries_tenant_candidate", table_name=t)
    op.drop_index("ix_blacklist_entries_tenant_status", table_name=t)
    op.drop_index(op.f("ix_blacklist_entries_status"), table_name=t)
    op.drop_index(op.f("ix_blacklist_entries_candidate_id"), table_name=t)
    op.drop_index(op.f("ix_blacklist_entries_tenant_id"), table_name=t)
    op.drop_table(t)
