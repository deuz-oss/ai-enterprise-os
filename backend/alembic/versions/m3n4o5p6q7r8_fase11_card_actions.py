"""Sisa Fase 11 — card/actions di chat_messages

Revision ID: m3n4o5p6q7r8
Revises: l3m4n5o6p7q8
Create Date: 2026-08-25 14:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m3n4o5p6q7r8"
down_revision: str | None = "l3m4n5o6p7q8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(sa.Column("message_type", sa.String(length=20), nullable=False, server_default="text"))
        batch_op.add_column(sa.Column("card_data", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("actions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("actions")
        batch_op.drop_column("card_data")
        batch_op.drop_column("message_type")
