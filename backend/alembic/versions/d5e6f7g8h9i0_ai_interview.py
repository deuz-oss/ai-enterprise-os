"""PRD v3.1 Patch 4: AI Interview -- ai_interview_templates + ai_interview_responses

Revision ID: d5e6f7g8h9i0
Revises: b3c4d5e6f7g8
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7g8h9i0"
down_revision: str | None = "b3c4d5e6f7g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_interview_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_order_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(length=20), server_default="async_text", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("questions_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("criteria_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["job_order_id"], ["job_orders.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_interview_templates_tenant_id"),
        "ai_interview_templates",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_templates_job_order_id"),
        "ai_interview_templates",
        ["job_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_templates_status"), "ai_interview_templates", ["status"], unique=False
    )

    op.create_table(
        "ai_interview_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_order_id", sa.Uuid(), nullable=True),
        sa.Column("invite_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="diundang", nullable=False),
        sa.Column("answers_json", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("ai_score_overall", sa.Integer(), nullable=True),
        sa.Column("ai_score_breakdown_json", sa.Text(), nullable=True),
        sa.Column("ai_narrative", sa.Text(), nullable=True),
        sa.Column("ai_model", sa.String(length=120), nullable=True),
        sa.Column(
            "review_status", sa.String(length=20), server_default="menunggu_review", nullable=False
        ),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["template_id"], ["ai_interview_templates.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["job_order_id"], ["job_orders.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_token", name="uq_ai_interview_responses_invite_token"),
    )
    op.create_index(
        op.f("ix_ai_interview_responses_tenant_id"),
        "ai_interview_responses",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_responses_template_id"),
        "ai_interview_responses",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_responses_candidate_id"),
        "ai_interview_responses",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_responses_job_order_id"),
        "ai_interview_responses",
        ["job_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_responses_invite_token"),
        "ai_interview_responses",
        ["invite_token"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interview_responses_status"), "ai_interview_responses", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_ai_interview_responses_review_status"),
        "ai_interview_responses",
        ["review_status"],
        unique=False,
    )
    op.create_index(
        "ix_ai_interview_resp_tenant_status",
        "ai_interview_responses",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_ai_interview_resp_tenant_review",
        "ai_interview_responses",
        ["tenant_id", "review_status"],
        unique=False,
    )


def downgrade() -> None:
    t = "ai_interview_responses"
    op.drop_index("ix_ai_interview_resp_tenant_review", table_name=t)
    op.drop_index("ix_ai_interview_resp_tenant_status", table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_review_status"), table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_status"), table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_invite_token"), table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_job_order_id"), table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_candidate_id"), table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_template_id"), table_name=t)
    op.drop_index(op.f("ix_ai_interview_responses_tenant_id"), table_name=t)
    op.drop_table(t)

    t2 = "ai_interview_templates"
    op.drop_index(op.f("ix_ai_interview_templates_status"), table_name=t2)
    op.drop_index(op.f("ix_ai_interview_templates_job_order_id"), table_name=t2)
    op.drop_index(op.f("ix_ai_interview_templates_tenant_id"), table_name=t2)
    op.drop_table(t2)
