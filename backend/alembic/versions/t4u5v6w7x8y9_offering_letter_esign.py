"""PRD v3.0 §4: surat penawaran (offering letter) + esign per placement

Revision ID: t4u5v6w7x8y9
Revises: s3t0u1v2w3x4
Create Date: 2026-08-30 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "t4u5v6w7x8y9"
down_revision: str | None = "s3t0u1v2w3x4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("placements") as batch:
        batch.add_column(
            sa.Column("offering_letter_object_key", sa.String(length=500), nullable=True)
        )
        batch.add_column(sa.Column("offering_signed_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("esign_requests") as batch:
        batch.add_column(sa.Column("placement_id", sa.Uuid(), nullable=True))
        batch.alter_column("contract_id", existing_type=sa.Uuid(), nullable=True)
        batch.create_foreign_key(
            "fk_esign_requests_placement_id", "placements", ["placement_id"], ["id"]
        )
    op.create_index(
        op.f("ix_esign_requests_placement_id"), "esign_requests", ["placement_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_esign_requests_placement_id"), table_name="esign_requests")
    with op.batch_alter_table("esign_requests") as batch:
        batch.drop_constraint("fk_esign_requests_placement_id", type_="foreignkey")
        batch.alter_column("contract_id", existing_type=sa.Uuid(), nullable=False)
        batch.drop_column("placement_id")
    with op.batch_alter_table("placements") as batch:
        batch.drop_column("offering_signed_at")
        batch.drop_column("offering_letter_object_key")
