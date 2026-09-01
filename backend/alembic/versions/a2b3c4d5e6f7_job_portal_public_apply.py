"""PRD v3.1 Patch 5: Job Portal — job_orders.is_public/public_client_label/
screening_questions_json, placements.application_token/screening_answers.

Revision ID: a2b3c4d5e6f7
Revises: z1b2c3d4e5f6
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "z1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(
            sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False)
        )
        batch.add_column(sa.Column("public_client_label", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("screening_questions_json", sa.Text(), nullable=True))
    with op.batch_alter_table("placements") as batch:
        batch.add_column(sa.Column("application_token", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("screening_answers", sa.Text(), nullable=True))
        batch.create_unique_constraint("uq_placements_application_token", ["application_token"])


def downgrade() -> None:
    with op.batch_alter_table("placements") as batch:
        batch.drop_constraint("uq_placements_application_token", type_="unique")
        batch.drop_column("screening_answers")
        batch.drop_column("application_token")
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("screening_questions_json")
        batch.drop_column("public_client_label")
        batch.drop_column("is_public")
