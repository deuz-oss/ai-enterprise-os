"""Fase 20 item 4: kolom esign_requests.agreement_id -- perluasan esign
untuk Agreement klien, sama pola dengan t4u5v6w7x8y9 (yang menambah
placement_id sebagai link kedua). Sekarang tepat satu dari
contract_id/placement_id/agreement_id terisi, sisanya NULL.

Revision ID: 0adce2836804
Revises: be1bef15724c
Create Date: 2026-09-04 07:54:14.666866
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0adce2836804"
down_revision: str | None = "be1bef15724c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("esign_requests") as batch:
        batch.add_column(sa.Column("agreement_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_esign_requests_agreement_id", "agreements", ["agreement_id"], ["id"]
        )
    op.create_index(
        op.f("ix_esign_requests_agreement_id"), "esign_requests", ["agreement_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_esign_requests_agreement_id"), table_name="esign_requests")
    with op.batch_alter_table("esign_requests") as batch:
        batch.drop_constraint("fk_esign_requests_agreement_id", type_="foreignkey")
        batch.drop_column("agreement_id")
