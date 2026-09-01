"""PRD v3.1 Patch 2: pipeline rekrutmen diperluas — job_orders.requires_ojt,
placements.ojt_start_date/ojt_end_date, interview_schedules.interview_type.
PlacementStatus sendiri disimpan native_enum=False (kolom String) jadi
penambahan nilai enum baru tidak butuh migrasi skema, cuma di level Python.

Revision ID: y0a1b2c3d4e5
Revises: x8y9z0a1b2c3
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "y0a1b2c3d4e5"
down_revision: str | None = "x8y9z0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(
            sa.Column("requires_ojt", sa.Boolean(), server_default=sa.text("false"), nullable=False)
        )
    with op.batch_alter_table("placements") as batch:
        batch.add_column(sa.Column("ojt_start_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("ojt_end_date", sa.Date(), nullable=True))
    with op.batch_alter_table("interview_schedules") as batch:
        batch.add_column(
            sa.Column(
                "interview_type",
                sa.String(length=20),
                server_default="internal",
                nullable=False,
            )
        )
    op.create_index(
        "ix_interview_schedules_interview_type",
        "interview_schedules",
        ["interview_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interview_schedules_interview_type", table_name="interview_schedules")
    with op.batch_alter_table("interview_schedules") as batch:
        batch.drop_column("interview_type")
    with op.batch_alter_table("placements") as batch:
        batch.drop_column("ojt_end_date")
        batch.drop_column("ojt_start_date")
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("requires_ojt")
