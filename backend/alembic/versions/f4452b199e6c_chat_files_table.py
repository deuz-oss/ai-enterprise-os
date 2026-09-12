"""chat_files_table

File attachment untuk chat (roadmap riset arsitektur Mattermost, item
terakhir dari fase "copy vs skip"). `message_id` nullable -- file diupload
berdiri sendiri dulu (`POST /chat/channels/{id}/files`), baru ditempel ke
pesan saat `POST /chat/channels/{id}/messages` menyertakan `file_ids`
(meniru alur upload-lalu-attach Mattermost, bukan multipart+JSON sekaligus,
supaya UI bisa tampilkan progres unggah sebelum tombol kirim ditekan).

RLS ditambahkan langsung di migrasi yang sama dengan pembuatan tabel, pola
yang sama dipakai sejak `9349e6c0fcac_offering_settings_table.py`.

Revision ID: f4452b199e6c
Revises: 600bd504ad4e
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4452b199e6c"
down_revision: str | None = "600bd504ad4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "chat_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("uploader_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["chat_channels.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_files_channel_id"), "chat_files", ["channel_id"], unique=False)
    op.create_index(op.f("ix_chat_files_message_id"), "chat_files", ["message_id"], unique=False)
    op.create_index(op.f("ix_chat_files_tenant_id"), "chat_files", ["tenant_id"], unique=False)

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE chat_files ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE chat_files FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON chat_files
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON chat_files"))
        op.execute(sa.text("ALTER TABLE chat_files NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE chat_files DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_chat_files_tenant_id"), table_name="chat_files")
    op.drop_index(op.f("ix_chat_files_message_id"), table_name="chat_files")
    op.drop_index(op.f("ix_chat_files_channel_id"), table_name="chat_files")
    op.drop_table("chat_files")
