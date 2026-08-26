"""Fase 13: talent pool & CV standardization (cv_intakes, standard_cv_versions, tenant_cv_branding)

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-08-26 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p6q7r8s9t0u1"
down_revision: str | None = "o5p6q7r8s9t0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cv_intakes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column(
            "doc_kind",
            sa.Enum(
                "pdf_text",
                "pdf_scan",
                "docx",
                "image",
                name="cvdockind",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "terunggah",
                "diproses",
                "menunggu_review",
                "finalisasi",
                "gagal",
                name="intakestatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("extracted", sa.Text(), nullable=True),
        sa.Column("confidences", sa.Text(), nullable=True),
        sa.Column("needs_review", sa.Text(), nullable=True),
        sa.Column("reviewed_fields", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("readiness", sa.String(length=30), nullable=True),
        sa.Column(
            "tp_status",
            sa.Enum(
                "baru",
                "diproses",
                "placed",
                "non_aktif",
                name="talentpoolstatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cv_intakes_tenant_id"), "cv_intakes", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_cv_intakes_candidate_id"), "cv_intakes", ["candidate_id"], unique=False
    )
    op.create_index(op.f("ix_cv_intakes_status"), "cv_intakes", ["status"], unique=False)
    op.create_index(op.f("ix_cv_intakes_tp_status"), "cv_intakes", ["tp_status"], unique=False)

    op.create_table(
        "standard_cv_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("intake_id", sa.Uuid(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("locked_for_placement_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["intake_id"], ["cv_intakes.id"]),
        sa.ForeignKeyConstraint(["locked_for_placement_id"], ["placements.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "seq", name="uq_cv_version_seq"),
    )
    op.create_index(
        op.f("ix_standard_cv_versions_tenant_id"),
        "standard_cv_versions",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_standard_cv_versions_candidate_id"),
        "standard_cv_versions",
        ["candidate_id"],
        unique=False,
    )

    op.create_table(
        "tenant_cv_branding",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("accent_color", sa.String(length=9), nullable=False),
        sa.Column("footer_text", sa.String(length=255), nullable=False),
        sa.Column("show_photo", sa.Boolean(), nullable=False),
        sa.Column("logo_object_key", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenant_cv_branding_tenant_id"), "tenant_cv_branding", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("tenant_cv_branding")
    op.drop_table("standard_cv_versions")
    op.drop_table("cv_intakes")
