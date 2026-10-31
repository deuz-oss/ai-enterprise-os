"""ai_interview_settings: foto referensi avatar pewawancara AI per tenant.

Dulu foto wajah avatar (Fase 67) hanya dari env `AVATAR_REFERENCE_IMAGE` di
avatar-worker -- satu wajah untuk semua tenant. Kolom baru menyimpan object
key JPEG ternormalisasi milik tenant; kosong = worker memakai foto env.

Hanya dua kolom ini: autogenerate di SQLite juga mendeteksi selisih indeks/
tipe lama yang bukan bagian perubahan ini (sudah dibuang).

Revision ID: 57b5ffb1923e
Revises: 46ebfc27d235
Create Date: 2026-10-31 00:34:58.271484

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "57b5ffb1923e"
down_revision: str | None = "46ebfc27d235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_interview_settings", sa.Column("avatar_image_key", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "ai_interview_settings",
        sa.Column("avatar_image_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_interview_settings", "avatar_image_updated_at")
    op.drop_column("ai_interview_settings", "avatar_image_key")
