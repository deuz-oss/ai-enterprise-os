"""Polish: foto kandidat untuk CV standar + halaman workspace (page tree Notion)

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-08-26 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r8s9t0u1v2w3"
down_revision: str | None = "q7r8s9t0u1v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("photo_object_key", sa.String(length=500), nullable=True))

    op.create_table(
        "notion_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["parent_id"], ["notion_pages.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notion_pages_tenant_id"), "notion_pages", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_notion_pages_parent_id"), "notion_pages", ["parent_id"], unique=False)


def downgrade() -> None:
    op.drop_table("notion_pages")
    with op.batch_alter_table("candidates") as batch:
        batch.drop_column("photo_object_key")
