"""Fase 28: tabel payment_intents -- jembatan checkout Xendit <-> efek bisnis
(aktivasi subscription / top-up saldo), diselesaikan lewat webhook.

SENGAJA TANPA RLS, sama seperti `payroll_run_tokens`/`ai_interview_responses`
(lihat `g8h9i0j1k2l3_extend_rls_coverage.py`): baris ini dicari webhook
Xendit lewat `provider_invoice_id` SEBELUM tenant diketahui/`set_tenant()`
dipanggil -- RLS FORCE akan mem-block lookup awal itu sendiri karena
`app.current_tenant` masih kosong di titik itu. Isolasi tenant untuk tabel
ini cukup lewat filter ORM otomatis (aktif begitu `set_tenant()` dipanggil
segera setelah baris ditemukan, pola sama `payroll/service.py::decide_by_token`).

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-05 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("provider_invoice_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_invoice_id", name="uq_payment_intent_invoice"),
    )
    op.create_index(op.f("ix_payment_intents_tenant_id"), "payment_intents", ["tenant_id"])
    op.create_index(
        op.f("ix_payment_intents_provider_invoice_id"), "payment_intents", ["provider_invoice_id"]
    )
    op.create_index(op.f("ix_payment_intents_status"), "payment_intents", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_intents_status"), table_name="payment_intents")
    op.drop_index(op.f("ix_payment_intents_provider_invoice_id"), table_name="payment_intents")
    op.drop_index(op.f("ix_payment_intents_tenant_id"), table_name="payment_intents")
    op.drop_table("payment_intents")
