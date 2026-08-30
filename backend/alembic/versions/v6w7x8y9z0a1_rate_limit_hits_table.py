"""rate_limit_hits: rate limiter login/reset pindah dari in-memory ke Postgres

Revision ID: v6w7x8y9z0a1
Revises: t4u5v6w7x8y9
Create Date: 2026-08-31 09:00:00.000000

Sebelumnya `SlidingWindowLimiter` (core/ratelimit.py) murni in-memory
per-proses — tidak dibagi antar worker/instance saat di-scale horizontal.
Tabel ini jadi tempat counter itu disimpan, dibagi lewat Postgres (sumber
kebenaran bersama yang sudah ada) alih-alih menambah infra baru (Redis).

Sengaja TIDAK masuk daftar RLS `BUSINESS_TABLES` di migrasi
`03c4cecd231b` — baris di sini bukan data tenant (rate-limit terjadi
pra-autentikasi, sebelum konteks tenant ada; key-nya IP/email).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v6w7x8y9z0a1"
down_revision: str | None = "t4u5v6w7x8y9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(length=50), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column(
            "hit_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ratelimit_ns_key_time",
        "rate_limit_hits",
        ["namespace", "key", "hit_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ratelimit_ns_key_time", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
