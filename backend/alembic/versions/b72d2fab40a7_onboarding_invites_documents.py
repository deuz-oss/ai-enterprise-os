"""onboarding_invites_documents

SENGAJA TIDAK ditambahkan ke daftar RLS `BUSINESS_TABLES` (lihat
`g8h9i0j1k2l3_extend_rls_coverage.py` dst.) -- `onboarding_invites` dicari
lewat token SEBELUM tenant diketahui, sama seperti `payroll_run_tokens`/
`payment_intents`/`ai_interview_responses`. Isolasi tenant cukup lewat
`set_tenant()` + filter ORM otomatis begitu baris ditemukan (lihat
`e1f2a3b4c5d6_fase28_payment_intents.py`).

Revision ID: b72d2fab40a7
Revises: 0149c3ce7aad
Create Date: 2026-09-06 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b72d2fab40a7"
down_revision: str | None = "0149c3ce7aad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "onboarding_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("placement_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "invited",
                "submitted",
                "applied",
                "revoked",
                name="onboardinginvitestatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("submitted_data_json", sa.Text(), nullable=True),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["placement_id"], ["placements.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_onboarding_invites_placement_id"),
        "onboarding_invites",
        ["placement_id"],
        unique=False,
    )

    op.create_table(
        "onboarding_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invite_id", sa.Uuid(), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "ktp",
                "npwp",
                "bpjs_kesehatan",
                "bpjs_ketenagakerjaan",
                "kartu_bpjs_kesehatan",
                "kartu_bpjs_ketenagakerjaan",
                "skck",
                "lainnya",
                name="hrdocumenttype",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["invite_id"], ["onboarding_invites.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_onboarding_documents_invite_id"),
        "onboarding_documents",
        ["invite_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_onboarding_documents_invite_id"), table_name="onboarding_documents")
    op.drop_table("onboarding_documents")
    op.drop_index(op.f("ix_onboarding_invites_placement_id"), table_name="onboarding_invites")
    op.drop_table("onboarding_invites")
