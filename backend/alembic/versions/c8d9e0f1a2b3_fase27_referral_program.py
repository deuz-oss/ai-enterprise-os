"""Fase 27: employees.referral_code, candidates.referred_by_employee_id,
tabel referral_program_settings + referral_rewards -- jalur sourcing
ketiga (referral), di samping Job Portal & Talent Pool.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-04 17:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch:
        batch.add_column(sa.Column("referral_code", sa.String(length=50), nullable=True))
    op.create_index(
        op.f("ix_employees_referral_code"), "employees", ["referral_code"], unique=False
    )

    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("referred_by_employee_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_candidates_referred_by_employee_id",
            "employees",
            ["referred_by_employee_id"],
            ["id"],
        )
    op.create_index(
        op.f("ix_candidates_referred_by_employee_id"),
        "candidates",
        ["referred_by_employee_id"],
        unique=False,
    )

    op.create_table(
        "referral_program_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reward_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_referral_program_settings_tenant_id"),
        "referral_program_settings",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("placement_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("eligible_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["placement_id"], ["placements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_referral_rewards_tenant_id"), "referral_rewards", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_referral_rewards_employee_id"), "referral_rewards", ["employee_id"], unique=False
    )
    op.create_index(
        op.f("ix_referral_rewards_candidate_id"), "referral_rewards", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_referral_rewards_placement_id"), "referral_rewards", ["placement_id"], unique=False
    )
    op.create_index(
        op.f("ix_referral_rewards_status"), "referral_rewards", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_referral_rewards_status"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_placement_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_candidate_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_employee_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_tenant_id"), table_name="referral_rewards")
    op.drop_table("referral_rewards")

    op.drop_index(
        op.f("ix_referral_program_settings_tenant_id"), table_name="referral_program_settings"
    )
    op.drop_table("referral_program_settings")

    op.drop_index(op.f("ix_candidates_referred_by_employee_id"), table_name="candidates")
    with op.batch_alter_table("candidates") as batch:
        batch.drop_constraint("fk_candidates_referred_by_employee_id", type_="foreignkey")
        batch.drop_column("referred_by_employee_id")

    op.drop_index(op.f("ix_employees_referral_code"), table_name="employees")
    with op.batch_alter_table("employees") as batch:
        batch.drop_column("referral_code")
