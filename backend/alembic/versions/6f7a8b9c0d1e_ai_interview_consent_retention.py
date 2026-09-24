"""ai_interview_consent_retention

Fase 0 roadmap AI Interview (fondasi kepatuhan sebelum fitur rekaman suara):

- `ai_interview_responses`: bukti persetujuan kandidat (UU PDP No. 27/2022
  -- rekaman suara berpotensi data biometrik = data pribadi spesifik yang
  butuh persetujuan khusus), penarikan persetujuan, dan penanda pembersihan
  data (`data_purged_at`/`purge_reason`).
- `ai_interview_settings`: masa retensi per tenant. RLS langsung di migrasi
  yang sama (pola `17ea218b3149_ai_lead_briefs_table.py`).

Tidak ada backfill: respons lama tanpa `consent_given_at` tetap bisa dibaca
staf, tapi sesi kandidat yang BELUM dikirim wajib menyetujui dulu sebelum
melanjutkan (dicek di service, bukan constraint DB).

Batch mode supaya ALTER TABLE juga jalan di SQLite.

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-09-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f7a8b9c0d1e"
down_revision: str | None = "5e6f7a8b9c0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.add_column(
            sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("consent_version", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("data_purged_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("purge_reason", sa.String(length=30), nullable=True))

    op.create_table(
        "ai_interview_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_interview_settings_tenant_id"),
        "ai_interview_settings",
        ["tenant_id"],
        unique=False,
    )

    if not _is_pg():
        return
    op.execute(sa.text("ALTER TABLE ai_interview_settings ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE ai_interview_settings FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON ai_interview_settings
            USING (tenant_id::text = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
            """
        )
    )


def downgrade() -> None:
    if _is_pg():
        op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON ai_interview_settings"))
        op.execute(sa.text("ALTER TABLE ai_interview_settings NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE ai_interview_settings DISABLE ROW LEVEL SECURITY"))
    op.drop_index(op.f("ix_ai_interview_settings_tenant_id"), table_name="ai_interview_settings")
    op.drop_table("ai_interview_settings")
    with op.batch_alter_table("ai_interview_responses") as batch_op:
        batch_op.drop_column("purge_reason")
        batch_op.drop_column("data_purged_at")
        batch_op.drop_column("consent_withdrawn_at")
        batch_op.drop_column("consent_version")
        batch_op.drop_column("consent_given_at")
