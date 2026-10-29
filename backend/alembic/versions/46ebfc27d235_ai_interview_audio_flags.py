"""ai_interview_responses: audio_flags_json (cek ruangan & jawaban "bukan suara saya").

Sinyal kualitas audio interview suara untuk reviewer: hasil cek ruangan
pra-panggilan dan jawaban yang ditandai kandidat bukan suaranya (suara
latar/TV yang terbaca sebagai jawaban, uji browser 2026-10-29).

Revision ID: 46ebfc27d235
Revises: 46effe939a61
Create Date: 2026-10-29 20:50:01.052431

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "46ebfc27d235"
down_revision: str | None = "46effe939a61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_interview_responses", sa.Column("audio_flags_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_interview_responses", "audio_flags_json")
