"""ai_interview_recording

Fase 2 roadmap AI Interview: rekaman sesi suara (object key + ukuran) dan
transkrip versi dirapikan untuk dibaca reviewer. Transkrip mentah tetap di
`transcript_text` dan tetap satu-satunya dasar penilaian.

Batch mode supaya ALTER TABLE juga jalan di SQLite.

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-09-24 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a8b9c0d1e2f"
down_revision: str | None = "6f7a8b9c0d1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.add_column(sa.Column("transcript_clean", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("recording_object_key", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("recording_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.drop_column("recording_size_bytes")
        batch_op.drop_column("recording_object_key")
        batch_op.drop_column("transcript_clean")
