"""onboarding_requested_documents

Kolom baru `requested_document_types_json` di `onboarding_invites` --
daftar dokumen yang HR minta dari kandidat saat membuat undangan (pola
MYOHRIS "Setup job assessments for onboard": HR memilih dokumen apa saja
sebelum link dikirim, kandidat cuma melihat/mengunggah jenis yang diminta
itu -- sebelumnya candidate self-service SELALU menampilkan 3 jenis tetap
(KTP/NPWP/SKCK) apa pun kebutuhan job order-nya).

`HrDocumentType` (enum VARCHAR, `native_enum=False`, tanpa CHECK constraint
DB -- lihat `ba192dfbcc82_simplify_placement_pipeline.py`) juga ditambah 6
jenis dokumen umum Indonesia (KK, ijazah, SIM, buku tabungan, paklaring,
surat keterangan sehat) -- tidak perlu migrasi data, cuma penambahan nilai
yang valid di sisi aplikasi.

Revision ID: d4e5f6a7b8c9
Revises: 9349e6c0fcac
Create Date: 2026-09-07 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "9349e6c0fcac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "onboarding_invites",
        sa.Column(
            "requested_document_types_json",
            sa.Text(),
            nullable=False,
            server_default='["ktp", "npwp", "skck"]',
        ),
    )


def downgrade() -> None:
    op.drop_column("onboarding_invites", "requested_document_types_json")
