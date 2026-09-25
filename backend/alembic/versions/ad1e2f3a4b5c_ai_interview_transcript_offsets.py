"""ai_interview_transcript_offsets

Offset detik (relatif awal rekaman sesi) per baris transkrip suara real-time,
dikirim agent terpisah dari teks transkrip -- dipakai untuk memutar rekaman
tepat di kutipan bukti.

Batch mode supaya ALTER TABLE juga jalan di SQLite.

Revision ID: ad1e2f3a4b5c
Revises: 9c0d1e2f3a4b
Create Date: 2026-09-26 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad1e2f3a4b5c"
down_revision: str | None = "9c0d1e2f3a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.add_column(sa.Column("transcript_offsets_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.drop_column("transcript_offsets_json")
