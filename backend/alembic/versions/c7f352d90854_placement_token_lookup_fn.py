"""Fungsi resolve_placement_tenant(token) -- perbaiki gap fungsional yang
ditemukan saat memperluas RLS (g8h9i0j1k2l3)

`job_portal/service.py::get_application_status()` (endpoint publik
`GET /public/applications/{token}`) mencari `Placement` by
`application_token` SEBELUM tenant diketahui (baris harus ditemukan dulu
untuk tahu tenant-nya) -- pola yang sama seperti `ai_interview_responses`/
`payroll_run_tokens`, TAPI `placements` sudah RLS-covered sejak migrasi
awal (`03c4cecd231b`) untuk penggunaan lain yang legit (staf melihat daftar
placement per tenant). Beda dari 2 tabel itu, `placements` TIDAK bisa
dikecualikan dari RLS begitu saja -- proteksi itu tetap dibutuhkan untuk
akses staf.

Sekarang setelah role app (`aeos_app`, lihat docker-compose.yml) benar-benar
non-superuser dan RLS benar-benar berlaku (bukan lagi didiamkan oleh
role superuser), lookup awal ini akan SELALU mengembalikan 0 baris di
Postgres -- `app.current_tenant` belum ke-set saat query itu jalan, RLS
memblokir semua baris tanpa kecuali.

Perbaikan: fungsi SQL sempit, `SECURITY DEFINER` (berjalan sebagai pemilik
fungsi = role migrasi/superuser, yang SELALU melewati RLS terlepas dari
FORCE), HANYA mengembalikan `tenant_id` untuk satu token -- permukaan yang
sangat sempit (bukan bypass RLS umum). `aeos_app` diberi EXECUTE, bukan
akses langsung ke tabel tanpa RLS. Dipanggil dari service HANYA di
Postgres (SQLite dev/test tidak punya RLS sama sekali, query ORM biasa
tetap benar di sana -- lihat cabang dialect di service.py).

Revision ID: c7f352d90854
Revises: g8h9i0j1k2l3
Create Date: 2026-09-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7f352d90854"
down_revision: str | None = "g8h9i0j1k2l3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_pg():
        return
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION resolve_placement_tenant(p_token text)
            RETURNS uuid
            LANGUAGE sql
            SECURITY DEFINER
            STABLE
            SET search_path = public
            AS $$
                SELECT tenant_id FROM placements
                WHERE application_token = p_token
                LIMIT 1
            $$;
            """
        )
    )
    op.execute(sa.text("REVOKE ALL ON FUNCTION resolve_placement_tenant(text) FROM PUBLIC"))
    # Defensive: kalau role aeos_app belum ada (mis. migrasi jalan sebelum
    # deploy/pg/init-roles.sh sempat bikin role-nya), jangan gagalkan
    # migrasi -- GRANT ulang manual sekali role-nya ada.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aeos_app') THEN
                    GRANT EXECUTE ON FUNCTION resolve_placement_tenant(text) TO aeos_app;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    if not _is_pg():
        return
    op.execute(sa.text("DROP FUNCTION IF EXISTS resolve_placement_tenant(text)"))
