"""PRD v3.1 Patch 3: Job Order field tambahan (request_id/date, area,
contract_duration_months, gross_salary, business_status)

Revision ID: x8y9z0a1b2c3
Revises: v6w7x8y9z0a1
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "x8y9z0a1b2c3"
down_revision: str | None = "v6w7x8y9z0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.add_column(sa.Column("request_id", sa.String(length=50), nullable=True))
        batch.add_column(
            sa.Column(
                "request_date",
                sa.Date(),
                server_default=sa.text("CURRENT_DATE"),
                nullable=False,
            )
        )
        batch.add_column(sa.Column("area", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("contract_duration_months", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("gross_salary", sa.Numeric(14, 2), nullable=True))
        batch.add_column(
            sa.Column(
                "business_status", sa.String(length=20), server_default="dibuka", nullable=False
            )
        )
    op.create_index("ix_job_orders_request_id", "job_orders", ["request_id"], unique=False)
    op.create_index("ix_job_orders_request_date", "job_orders", ["request_date"], unique=False)
    op.create_index(
        "ix_job_orders_business_status", "job_orders", ["business_status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_job_orders_business_status", table_name="job_orders")
    op.drop_index("ix_job_orders_request_date", table_name="job_orders")
    op.drop_index("ix_job_orders_request_id", table_name="job_orders")
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_column("business_status")
        batch.drop_column("gross_salary")
        batch.drop_column("contract_duration_months")
        batch.drop_column("area")
        batch.drop_column("request_date")
        batch.drop_column("request_id")
