"""chat_unread_counters

Ganti model unread chat dari scan tabel `chat_messages` tiap render
(hitung count/max(created_at) per channel per user -- O(n) dan salah secara
semantik karena "last read" dulu dipakai proxy dari pesan terakhir yang
dikirim USER SENDIRI, bukan kapan dia terakhir melihat channel) jadi model
counter ala Mattermost:

- `chat_channels.total_msg_count`: jumlah pesan channel, naik tiap kirim.
- `chat_channel_members.msg_count`: snapshot total_msg_count saat user
  terakhir "melihat" channel (endpoint view/read-all).
- `chat_channel_members.mention_count`: jumlah mention belum dibaca,
  di-reset ke 0 saat channel dilihat.
- `chat_channel_members.last_viewed_at`: timestamp lihat terakhir (UI only).

unread_count = total_msg_count - msg_count (di-clamp >= 0 di application code).

Revision ID: 704a96328f85
Revises: 2dbfdfcc8679
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "704a96328f85"
down_revision: str | None = "2dbfdfcc8679"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_channels") as batch:
        batch.add_column(
            sa.Column("total_msg_count", sa.Integer(), server_default="0", nullable=False)
        )
    with op.batch_alter_table("chat_channel_members") as batch:
        batch.add_column(sa.Column("msg_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(
            sa.Column("mention_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True))
    # Backfill total_msg_count dari data existing agar unread tidak salah
    # dihitung untuk channel yang sudah punya riwayat pesan.
    op.execute(
        """
        UPDATE chat_channels
        SET total_msg_count = (
            SELECT COUNT(*) FROM chat_messages
            WHERE chat_messages.channel_id = chat_channels.id
              AND chat_messages.deleted_at IS NULL
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("chat_channel_members") as batch:
        batch.drop_column("last_viewed_at")
        batch.drop_column("mention_count")
        batch.drop_column("msg_count")
    with op.batch_alter_table("chat_channels") as batch:
        batch.drop_column("total_msg_count")
