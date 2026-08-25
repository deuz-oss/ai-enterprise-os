"""Fase 9a: payrol dua jalur (run_type) + token approval klien

Revision ID: h9i0j1k2l3m4
Revises: g1h2i3j4k5l6
Create Date: 2026-08-25 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h9i0j1k2l3m4"
down_revision: str | None = "g1h2i3j4k5l6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Kolom run_type & client_id pada payroll_runs (status tetap VARCHAR,
    # nilai enum baru tidak membutuhkan DDL karena native_enum=False).
    # Batch mode agar FK bisa dibuat di SQLite.
    with op.batch_alter_table("payroll_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "run_type",
                sa.Enum(
                    "internal",
                    "proyek",
                    name="payrollruntype",
                    native_enum=False,
                    length=50,
                ),
                server_default="internal",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("client_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_payroll_runs_client_id_clients", "clients", ["client_id"], ["id"]
        )
    op.create_index(op.f("ix_payroll_runs_run_type"), "payroll_runs", ["run_type"], unique=False)

    op.create_table(
        "payroll_run_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_name", sa.String(length=255), nullable=True),
        sa.Column("decision_note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["payroll_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_payroll_token_hash"),
    )
    op.create_index(
        op.f("ix_payroll_run_tokens_tenant_id"), "payroll_run_tokens", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_payroll_run_tokens_run_id"), "payroll_run_tokens", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_payroll_run_tokens_expires_at"),
        "payroll_run_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("payroll_run_tokens")
    op.drop_index(op.f("ix_payroll_runs_run_type"), table_name="payroll_runs")
    with op.batch_alter_table("payroll_runs") as batch_op:
        batch_op.drop_constraint("fk_payroll_runs_client_id_clients", type_="foreignkey")
        batch_op.drop_column("client_id")
        batch_op.drop_column("run_type")
