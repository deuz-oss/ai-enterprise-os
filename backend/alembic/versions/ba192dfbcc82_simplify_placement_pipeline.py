"""simplify_placement_pipeline

Menyederhanakan `PlacementStatus` (11 tahap dari 13) atas umpan balik
langsung dari domain owner (2026-09-07): `sent_to_client`+`client_screening`
lebur ke `submitted`, `proposed`+`accepted` lebur jadi `offering`. Baris
yang sudah ada di kolom `status` (VARCHAR biasa, `native_enum=False` --
tidak ada CHECK constraint DB) direstorasi ke nilai barunya supaya tidak
ada placement yang "nyangkut" di status yang sudah tidak dikenal FE.

Kolom baru `rejection_note` (nullable) -- alasan gagal/batal, pengganti
2 tahap-antara yang dibuang sebagai jejak KENAPA kandidat gugur.

Revision ID: ba192dfbcc82
Revises: b72d2fab40a7
Create Date: 2026-09-07 08:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ba192dfbcc82"
down_revision: str | None = "b72d2fab40a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

placements = sa.table("placements", sa.column("status", sa.String))


def upgrade() -> None:
    op.add_column("placements", sa.Column("rejection_note", sa.Text(), nullable=True))
    op.execute(
        placements.update()
        .where(placements.c.status.in_(["dikirim_ke_klien", "screening_klien"]))
        .values(status="disubmit")
    )
    op.execute(
        placements.update()
        .where(placements.c.status.in_(["diusulkan", "disetujui_klien"]))
        .values(status="offering")
    )


def downgrade() -> None:
    # Data remap TIDAK dibalik -- nilai asal ("dikirim_ke_klien" vs
    # "screening_klien", "diusulkan" vs "disetujui_klien") sudah hilang
    # begitu digabung, tidak determinable untuk direkonstruksi.
    op.drop_column("placements", "rejection_note")
