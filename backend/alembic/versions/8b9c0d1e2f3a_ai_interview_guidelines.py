"""ai_interview_guidelines

Fase 4 roadmap AI Interview: pedoman percakapan per template (pasangan
"jika kandidat ... -> jawab ...") untuk agen suara real-time. Pengaturan
pertanyaan susulan per pertanyaan cukup di `questions_json` (tanpa kolom).

Batch mode supaya ALTER TABLE juga jalan di SQLite.

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-09-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b9c0d1e2f3a"
down_revision: str | None = "7a8b9c0d1e2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_interview_templates") as batch_op:
        batch_op.add_column(sa.Column("guidelines_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_interview_templates") as batch_op:
        batch_op.drop_column("guidelines_json")
