"""Fase 21 item 1: job_orders.benefits_json/working_days_json/
working_hours_start/working_hours_end -- dulunya numpang di teks bebas
description/requirements. Fase 21 item 2: placements.offering_call_done/
offering_call_at -- aksi offering call tercatat terpisah dari offering
letter+esign yang sudah ada.

Revision ID: 65e9eb9bf191
Revises: 0adce2836804
Create Date: 2026-09-04 09:57:40.353824
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "65e9eb9bf191"
down_revision: str | None = "0adce2836804"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(sa.Column("benefits_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("working_days_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("working_hours_start", sa.Time(), nullable=True))
        batch.add_column(sa.Column("working_hours_end", sa.Time(), nullable=True))
    with op.batch_alter_table("placements") as batch:
        batch.add_column(
            sa.Column(
                "offering_call_done", sa.Boolean(), server_default=sa.text("false"), nullable=False
            )
        )
        batch.add_column(sa.Column("offering_call_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("placements") as batch:
        batch.drop_column("offering_call_at")
        batch.drop_column("offering_call_done")
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("working_hours_end")
        batch.drop_column("working_hours_start")
        batch.drop_column("working_days_json")
        batch.drop_column("benefits_json")
