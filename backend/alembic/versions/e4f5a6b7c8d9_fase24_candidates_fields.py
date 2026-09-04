"""Fase 24: candidates field tambahan hasil audit MYOHRIS + skills_json
terstruktur + tabel candidate_experiences (riwayat per posisi).

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-04 16:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("skills_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reference", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("gender", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("current_position", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("birthdate", sa.Date(), nullable=True))
        batch.add_column(sa.Column("birthplace", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("address", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("ktp_no", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("marital_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("blood_type", sa.String(length=5), nullable=True))
        batch.add_column(sa.Column("religion", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("languages_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("position_pool", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("job_level", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("school", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("education_level", sa.String(length=120), nullable=True))
    op.create_index(op.f("ix_candidates_reference"), "candidates", ["reference"], unique=False)

    op.create_table(
        "candidate_experiences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("position", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_experiences_tenant_id"),
        "candidate_experiences",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_experiences_candidate_id"),
        "candidate_experiences",
        ["candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_candidate_experiences_candidate_id"), table_name="candidate_experiences")
    op.drop_index(op.f("ix_candidate_experiences_tenant_id"), table_name="candidate_experiences")
    op.drop_table("candidate_experiences")

    op.drop_index(op.f("ix_candidates_reference"), table_name="candidates")
    with op.batch_alter_table("candidates") as batch:
        batch.drop_column("education_level")
        batch.drop_column("school")
        batch.drop_column("job_level")
        batch.drop_column("position_pool")
        batch.drop_column("description")
        batch.drop_column("languages_json")
        batch.drop_column("religion")
        batch.drop_column("blood_type")
        batch.drop_column("marital_status")
        batch.drop_column("ktp_no")
        batch.drop_column("address")
        batch.drop_column("birthplace")
        batch.drop_column("birthdate")
        batch.drop_column("current_position")
        batch.drop_column("gender")
        batch.drop_column("reference")
        batch.drop_column("skills_json")
