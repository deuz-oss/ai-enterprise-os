"""rates ber-versi untuk pajak, BPJS, billing, bank fee (NFR §11)

Revision ID: g1h2i3j4k5l6
Revises: b4d5e6f7a8b9
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g1h2i3j4k5l6"
down_revision: str | None = "b4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pph21_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("ptkp_diri", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("ptkp_kawin", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("ptkp_tanggungan", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("max_tanggungan", sa.Integer(), nullable=False),
        sa.Column("pasal17_brackets", sa.JSON(), nullable=False),
        sa.Column("ter_a", sa.JSON(), nullable=False),
        sa.Column("ter_b", sa.JSON(), nullable=False),
        sa.Column("ter_c", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("effective_from", name="uq_pph21_effective"),
    )
    op.create_index(
        op.f("ix_pph21_configs_effective_from"), "pph21_configs", ["effective_from"], unique=False
    )

    op.create_table(
        "bpjs_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("kesehatan_employer", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("kesehatan_employee", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("kesehatan_cap", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("jht_employer", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("jht_employee", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("jp_employer", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("jp_employee", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("jp_cap", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("jkm_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("jkk_rates", sa.JSON(), nullable=False),
        sa.Column("default_jkk_category", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("effective_from", name="uq_bpjs_effective"),
    )
    op.create_index(
        op.f("ix_bpjs_configs_effective_from"), "bpjs_configs", ["effective_from"], unique=False
    )

    op.create_table(
        "billing_tax_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("ppn_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("pph23_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("due_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("effective_from", name="uq_billing_effective"),
    )
    op.create_index(
        op.f("ix_billing_tax_configs_effective_from"),
        "billing_tax_configs",
        ["effective_from"],
        unique=False,
    )

    op.create_table(
        "bank_fee_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("fee", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("is_mandiri_group", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_name", name="uq_bank_fee_name"),
    )

    # Snapshot rate untuk konsistensi historis per payroll run
    op.add_column("payroll_runs", sa.Column("pph21_snapshot", sa.JSON(), nullable=True))
    op.add_column("payroll_runs", sa.Column("bpjs_snapshot", sa.JSON(), nullable=True))

    # Seed versi awal dari konstanta kode (fallback yang sudah teruji)
    conn = op.get_bind()
    # PPh21 2025
    from datetime import date

    from app.modules.bpjs.engine import (
        DEFAULT_JKK_CATEGORY,
        JHT_EMPLOYEE,
        JHT_EMPLOYER,
        JKK_RATES,
        JKM_RATE,
        JP_EMPLOYEE,
        JP_EMPLOYER,
        JP_SALARY_CAP,
        KESEHATAN_EMPLOYEE,
        KESEHATAN_EMPLOYER,
        KESEHATAN_SALARY_CAP,
    )
    from app.modules.finance.tax_config import (
        DEFAULT_DUE_DAYS,
        DEFAULT_PPH23_RATE,
        DEFAULT_PPN_RATE,
    )
    from app.modules.payroll.tax import (
        MAX_TANGGUNGAN,
        PASAL_17_BRACKETS,
        PTKP_DIRI_SENDIRI,
        PTKP_KAWIN,
        PTKP_TANGGUNGAN,
        TER_A,
        TER_B,
        TER_C,
    )

    def _ser_brackets(brackets):
        # ubah inf -> None agar JSON serializable
        return [[None if upper == float("inf") else upper, rate] for upper, rate in brackets]

    pph21_id = "00000000-0000-0000-0000-000000000001"
    # .bindparams(**kwargs) (bukan dict kedua ke conn.execute) supaya
    # SQLAlchemy infer tipe dari nilai Python & proses bind sesuai dialek --
    # dict mentah ke conn.execute tidak melalui jalur itu, jadi str tanggal
    # gagal cast implisit ke kolom Date di Postgres.
    conn.execute(
        sa.text(
            "INSERT INTO pph21_configs (id, effective_from, ptkp_diri, ptkp_kawin, "
            "ptkp_tanggungan, "
            "max_tanggungan, pasal17_brackets, ter_a, ter_b, ter_c) "
            "VALUES (:id, :eff, :diri, :kawin, :tang, :max, :pasal, :a, :b, :c)"
        ).bindparams(
            # Kolom JSON: deklarasikan type_ eksplisit + kirim objek Python
            # asli (bukan json.dumps string) supaya SQLAlchemy serialize
            # sesuai dialek (Postgres json/jsonb vs SQLite text).
            sa.bindparam("pasal", type_=sa.JSON()),
            sa.bindparam("a", type_=sa.JSON()),
            sa.bindparam("b", type_=sa.JSON()),
            sa.bindparam("c", type_=sa.JSON()),
            id=pph21_id,
            eff=date(2025, 1, 1),
            diri=PTKP_DIRI_SENDIRI,
            kawin=PTKP_KAWIN,
            tang=PTKP_TANGGUNGAN,
            max=MAX_TANGGUNGAN,
            pasal=_ser_brackets(PASAL_17_BRACKETS),
            a=_ser_brackets(TER_A),
            b=_ser_brackets(TER_B),
            c=_ser_brackets(TER_C),
        )
    )

    bpjs_id = "00000000-0000-0000-0000-000000000002"
    conn.execute(
        sa.text(
            "INSERT INTO bpjs_configs (id, effective_from, kesehatan_employer, kesehatan_employee, "
            "kesehatan_cap, jht_employer, jht_employee, jp_employer, jp_employee, jp_cap, "
            "jkm_rate, jkk_rates, default_jkk_category) "
            "VALUES (:id, :eff, :ke, :ke2, :kecap, :jhte, :jhte2, :jpe, "
            ":jpe2, :jpcap, :jkm, :jkk, :jkk_category)"
        ).bindparams(
            sa.bindparam("jkk", type_=sa.JSON()),
            id=bpjs_id,
            eff=date(2025, 1, 1),
            ke=KESEHATAN_EMPLOYER,
            ke2=KESEHATAN_EMPLOYEE,
            kecap=KESEHATAN_SALARY_CAP,
            jhte=JHT_EMPLOYER,
            jhte2=JHT_EMPLOYEE,
            jpe=JP_EMPLOYER,
            jpe2=JP_EMPLOYEE,
            jpcap=JP_SALARY_CAP,
            jkm=JKM_RATE,
            jkk=JKK_RATES,
            jkk_category=DEFAULT_JKK_CATEGORY,
        )
    )

    billing_id = "00000000-0000-0000-0000-000000000003"
    conn.execute(
        sa.text(
            "INSERT INTO billing_tax_configs (id, effective_from, ppn_rate, pph23_rate, due_days) "
            "VALUES (:id, :eff, :ppn, :pph23, :due)"
        ).bindparams(
            id=billing_id,
            eff=date(2025, 1, 1),
            ppn=DEFAULT_PPN_RATE,
            pph23=DEFAULT_PPH23_RATE,
            due=DEFAULT_DUE_DAYS,
        )
    )

    # Bank fees default: Mandiri group gratis, lainnya 3500
    import uuid

    for name, is_mandiri in [
        ("Bank Mandiri", True),
        ("Bank BCA", False),
        ("Bank BNI", False),
        ("Bank BRI", False),
    ]:
        conn.execute(
            sa.text(
                "INSERT INTO bank_fee_configs (id, bank_name, fee, is_mandiri_group) "
                "VALUES (:id, :name, :fee, :is_m)"
            ).bindparams(
                id=str(uuid.uuid4()),
                name=name,
                fee=0 if is_mandiri else 3500,
                is_m=is_mandiri,
            )
        )


def downgrade() -> None:
    op.drop_column("payroll_runs", "bpjs_snapshot")
    op.drop_column("payroll_runs", "pph21_snapshot")
    op.drop_table("bank_fee_configs")
    op.drop_table("billing_tax_configs")
    op.drop_table("bpjs_configs")
    op.drop_table("pph21_configs")
