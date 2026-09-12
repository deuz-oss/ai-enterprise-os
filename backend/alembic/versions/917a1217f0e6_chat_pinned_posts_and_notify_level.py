"""chat_pinned_posts_and_notify_level

Dua item terakhir dari roadmap riset arsitektur Mattermost untuk chat:

- Pinned posts: `chat_messages.is_pinned/pinned_at/pinned_by_id`.
- Preferensi notifikasi per channel ala `notify_props` Mattermost:
  `chat_channel_members.notify_level` ("all" | "mentions" | "none").

Batch mode (pola sama `bd33f16a67b6_shift_and_address_fields.py`) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: 917a1217f0e6
Revises: f4452b199e6c
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "917a1217f0e6"
down_revision: str | None = "f4452b199e6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.add_column(
            sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False)
        )
        batch.add_column(sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("pinned_by_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_chat_messages_pinned_by_id", "users", ["pinned_by_id"], ["id"])
    with op.batch_alter_table("chat_channel_members") as batch:
        batch.add_column(
            sa.Column(
                "notify_level",
                sa.String(length=20),
                server_default="mentions",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_channel_members") as batch:
        batch.drop_column("notify_level")
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_constraint("fk_chat_messages_pinned_by_id", type_="foreignkey")
        batch.drop_column("pinned_by_id")
        batch.drop_column("pinned_at")
        batch.drop_column("is_pinned")
