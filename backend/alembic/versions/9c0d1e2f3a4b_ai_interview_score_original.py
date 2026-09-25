"""ai_interview_score_original

Fase 5 roadmap AI Interview: simpan skor AI asli saat reviewer
menyesuaikannya (dulu tertimpa), supaya kalibrasi "seberapa jauh AI
meleset dari penilaian manusia" bisa diukur per template.

Batch mode supaya ALTER TABLE juga jalan di SQLite.

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-09-25 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c0d1e2f3a4b"
down_revision: str | None = "8b9c0d1e2f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.add_column(sa.Column("ai_score_original", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.drop_column("ai_score_original")
