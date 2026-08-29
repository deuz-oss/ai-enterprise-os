"""PRD v3.0: metered billing_mode + interview + insurance one-to-many + faktur lengkap

Revision ID: s3t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-08-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s3t0u1v2w3x4"
down_revision: str | None = "r8s9t0u1v2w3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) tenants.billing_mode per-tenant override (PRD v3.0 §1)
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(
            sa.Column(
                "billing_mode", sa.String(length=20), server_default="inherit", nullable=False
            )
        )

    # 2) interview_schedules (PRD v3.0 §4)
    op.create_table(
        "interview_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_order_id", sa.Uuid(), nullable=False),
        sa.Column("interviewer_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("meeting_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="terjadwal", nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["job_order_id"], ["job_orders.id"]),
        sa.ForeignKeyConstraint(["interviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_schedules_tenant_id"), "interview_schedules", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_interview_schedules_scheduled_at"),
        "interview_schedules",
        ["scheduled_at"],
        unique=False,
    )

    # 3) employee_insurances one-to-many + bpjs valid_until (PRD v3.0 §5)
    op.create_table(
        "employee_insurances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="lainnya", nullable=False),
        sa.Column("policy_no", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="aktif", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("card_object_key", sa.String(length=500), nullable=True),
        sa.Column("policy_object_key", sa.String(length=500), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_insurances_tenant_id"), "employee_insurances", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_employee_insurances_employee_id"),
        "employee_insurances",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_insurances_valid_until"),
        "employee_insurances",
        ["valid_until"],
        unique=False,
    )

    with op.batch_alter_table("employees") as batch:
        batch.add_column(sa.Column("bpjs_kesehatan_valid_until", sa.Date(), nullable=True))
        batch.add_column(sa.Column("bpjs_ketenagakerjaan_valid_until", sa.Date(), nullable=True))
        # PRD v3.0 Workforce — kartu + status (asuransi legacy single;
        # one-to-many baru di employee_insurances)
        batch.add_column(sa.Column("bpjs_kesehatan_card_key", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column("bpjs_ketenagakerjaan_card_key", sa.String(length=500), nullable=True)
        )
        batch.add_column(sa.Column("bpjs_kesehatan_status", sa.String(length=20), nullable=True))
        batch.add_column(
            sa.Column("bpjs_ketenagakerjaan_status", sa.String(length=20), nullable=True)
        )
        batch.add_column(sa.Column("insurance_provider", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("insurance_policy_no", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("insurance_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("insurance_card_key", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("insurance_policy_key", sa.String(length=500), nullable=True))

    # 4) clients.activated_at (PRD v3.0 §3 auto prospek→aktif)
    with op.batch_alter_table("clients") as batch:
        batch.add_column(sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))

    # 5) invoices faktur lengkap 13 kolom (PRD v3.0 §7) — tambah semua yang ada di Base
    with op.batch_alter_table("invoices") as batch:
        for col, typ in [
            ("tax_invoice_no", sa.String(length=50)),
            ("tax_invoice_status", sa.String(length=30)),
            ("tax_invoice_date", sa.Date()),
            ("lawan_npwp", sa.String(length=20)),
            ("lawan_nama", sa.String(length=255)),
            ("lawan_alamat", sa.String(length=500)),
            ("dpp_amount", sa.Numeric(14, 2)),
            ("kode_transaksi", sa.String(length=3)),
            ("no_seri_faktur", sa.String(length=30)),
            ("faktur_pengganti_ref", sa.Uuid()),
            ("faktur_status_detail", sa.String(length=500)),
            ("efaktur_nsr", sa.String(length=100)),
            ("efaktur_qr_url", sa.String(length=500)),
            ("efaktur_payload", sa.Text()),
        ]:
            try:
                batch.add_column(sa.Column(col, typ, nullable=True))
            except Exception:
                pass

    # unique no_seri per tenant per tahun — via index
    # (SQLite tidak support partial, fallback index biasa)
    try:
        op.create_index(
            "ix_invoices_no_seri_tenant", "invoices", ["tenant_id", "no_seri_faktur"], unique=False
        )
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("ix_invoices_no_seri_tenant", table_name="invoices")
    except Exception:
        pass
    with op.batch_alter_table("invoices") as batch:
        for col in [
            "efaktur_payload",
            "efaktur_qr_url",
            "efaktur_nsr",
            "faktur_status_detail",
            "faktur_pengganti_ref",
            "no_seri_faktur",
            "kode_transaksi",
            "dpp_amount",
            "lawan_alamat",
            "lawan_nama",
            "lawan_npwp",
            "tax_invoice_date",
            "tax_invoice_status",
            "tax_invoice_no",
        ]:
            try:
                batch.drop_column(col)
            except Exception:
                pass
    with op.batch_alter_table("clients") as batch:
        try:
            batch.drop_column("activated_at")
        except Exception:
            pass
    with op.batch_alter_table("employees") as batch:
        for col in [
            "insurance_policy_key",
            "insurance_card_key",
            "insurance_status",
            "insurance_policy_no",
            "insurance_provider",
            "bpjs_ketenagakerjaan_status",
            "bpjs_kesehatan_status",
            "bpjs_ketenagakerjaan_card_key",
            "bpjs_kesehatan_card_key",
            "bpjs_ketenagakerjaan_valid_until",
            "bpjs_kesehatan_valid_until",
        ]:
            try:
                batch.drop_column(col)
            except Exception:
                pass
    op.drop_table("employee_insurances")
    op.drop_table("interview_schedules")
    with op.batch_alter_table("tenants") as batch:
        try:
            batch.drop_column("billing_mode")
        except Exception:
            pass
