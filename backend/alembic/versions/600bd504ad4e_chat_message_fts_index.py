"""chat_message_fts_index

Full-text search Postgres untuk `/chat/search` -- sebelumnya cuma ILIKE
(scan penuh tanpa index, `content.ilike('%q%')`), lambat begitu histori
chat membesar dan tidak bisa ranking relevansi.

Index GIN pada ekspresi `to_tsvector('simple', content)` (bukan kolom
generated tersimpan -- lebih simpel, tidak menambah kolom baru ke model
ORM). Config `simple` dipakai (bukan `english`) karena PostgreSQL tidak
punya stemmer/stopword bawaan utk Bahasa Indonesia -- `simple` cuma
tokenisasi tanpa stemming, tetap jauh lebih baik dari ILIKE (index-backed,
dukung multi-kata & ranking via `ts_rank`).

Postgres-only (lihat `_is_pg()`); SQLite dev/test tetap pakai ILIKE seperti
sebelumnya (cabang dialect di `chat/service.py::search_messages`).

Revision ID: 600bd504ad4e
Revises: 704a96328f85
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "600bd504ad4e"
down_revision: str | None = "704a96328f85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_pg():
        return
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_search_fts "
            "ON chat_messages USING GIN (to_tsvector('simple', content))"
        )
    )


def downgrade() -> None:
    if not _is_pg():
        return
    op.execute(sa.text("DROP INDEX IF EXISTS ix_chat_messages_search_fts"))
