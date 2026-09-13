"""lead_multi_currency

Fase 46 -- dukungan multi-currency untuk `Lead.estimated_value`,
terinspirasi `Deal.amount/currency/baseAmount/baseCurrency/fxRate`
trycompai/crm, disederhanakan untuk kebutuhan Aeos yang IDR-sentris:

- `currency`: kode ISO 4217 3 huruf, default "IDR" (baris lama otomatis
  tetap IDR, tidak ada migrasi data yang mengubah makna nilai lama).
- `fx_rate_to_idr`: snapshot kurs manual staf saat lead dibuat/diedit
  (BUKAN API kurs live), default 1 (identitas untuk IDR).

Batch mode (pola sama `bd33f16a67b6_shift_and_address_fields.py`) supaya
ALTER TABLE juga jalan di SQLite.

Revision ID: ca3907dde94f
Revises: fe77e86201de
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ca3907dde94f"
down_revision: str | None = "fe77e86201de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(
            sa.Column("currency", sa.String(length=3), server_default="IDR", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "fx_rate_to_idr",
                sa.Numeric(18, 6),
                server_default=sa.text("1"),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("fx_rate_to_idr")
        batch.drop_column("currency")
