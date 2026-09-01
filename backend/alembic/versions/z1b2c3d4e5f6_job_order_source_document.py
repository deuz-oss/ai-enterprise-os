"""PRD v3.1 Patch 3b: job_orders.source_document_object_key/file_name —
dokumen Job Order/Manpower Requisition sumber (upload + auto-fill + viewer).

Revision ID: z1b2c3d4e5f6
Revises: y0a1b2c3d4e5
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z1b2c3d4e5f6"
down_revision: str | None = "y0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(
            sa.Column("source_document_object_key", sa.String(length=500), nullable=True)
        )
        batch.add_column(
            sa.Column("source_document_file_name", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("source_document_file_name")
        batch.drop_column("source_document_object_key")
