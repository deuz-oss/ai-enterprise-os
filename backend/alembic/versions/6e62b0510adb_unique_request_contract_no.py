"""job_orders.request_id + employment_contracts.contract_no: tambah
UniqueConstraint(tenant_id, kolom) -- temuan audit 2026-09-02

`_generate_request_id()`/`_generate_contract_no()` generate nomor berbasis
`COUNT(*)` tanpa lock -- rawan tabrakan (baris terhapus bikin count turun,
atau dua request bersamaan baca count yang sama) DAN sebelum migrasi ini
TIDAK ADA apa pun di skema yang mencegah dua baris punya nomor identik --
kalau tabrakan terjadi, keduanya sukses tersimpan diam-diam (data rusak
tanpa error apa pun). Tabel lain yang generate nomor serupa
(`employees.employee_no`, `invoices.invoice_no`, `payment_requests.pr_number`)
SUDAH punya UniqueConstraint sejak awal -- dua ini yang tertinggal.

Dicek dulu sebelum migrasi ini ditulis: tidak ada duplikat di data
produksi/dev saat ini (`SELECT tenant_id, request_id, count(*) ... HAVING
count(*) > 1` = 0 baris, sama untuk contract_no) -- aman dijalankan.

Revision ID: 6e62b0510adb
Revises: c7f352d90854
Create Date: 2026-09-02 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "6e62b0510adb"
down_revision: str | None = "c7f352d90854"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_orders") as batch:
        batch.create_unique_constraint(
            "uq_job_order_tenant_request_id", ["tenant_id", "request_id"]
        )
    with op.batch_alter_table("employment_contracts") as batch:
        batch.create_unique_constraint(
            "uq_contract_tenant_contract_no", ["tenant_id", "contract_no"]
        )


def downgrade() -> None:
    with op.batch_alter_table("employment_contracts") as batch:
        batch.drop_constraint("uq_contract_tenant_contract_no", type_="unique")
    with op.batch_alter_table("job_orders") as batch:
        batch.drop_constraint("uq_job_order_tenant_request_id", type_="unique")
