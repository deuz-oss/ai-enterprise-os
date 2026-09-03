"""Guard: setiap tabel bisnis ber-`tenant_id` NOT NULL wajib punya RLS policy
Postgres aktif.

Ditulis setelah audit menemukan 34 tabel yang lahir pasca-migrasi RLS awal
(`03c4cecd231b`) tidak pernah ditambahkan ke daftar `BUSINESS_TABLES`-nya --
isolasinya diam-diam cuma bergantung pada filter ORM (fail-open, tidak
berlaku untuk bulk update/delete). Test ini memastikan tabel BARU
berikutnya tidak bisa lolos dengan gap yang sama tanpa test ini gagal.

Hanya berjalan kalau ada Postgres nyata (env `TEST_POSTGRES_URL`, atau
`DATABASE_URL` kalau dialeknya postgresql) -- SQLite (default test suite)
tidak punya konsep RLS sama sekali, jadi tidak bisa memverifikasi ini.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

# Tabel yang SENGAJA tidak punya RLS -- alasan didokumentasikan per baris,
# bukan daftar tanpa penjelasan. Tambah ke sini HANYA dengan alasan sekuat
# ini, jangan untuk menghindari test gagal.
EXCLUDED_TABLES = {
    # tenant_id nullable: akun platform_admin (tanpa tenant) & event
    # pra-login. Pola sama sejak migrasi RLS awal 03c4cecd231b.
    "users",
    "audit_logs",
    # Di-query via token publik SEBELUM set_tenant() dipanggil (baris harus
    # ditemukan dulu untuk tahu tenant-nya) -- RLS akan mem-block lookup
    # awal itu sendiri. Isolasi sudah benar lewat set_tenant() manual
    # segera setelah baris ditemukan (execution_options bypass ORM-level,
    # bukan RLS). Lihat alembic/versions/g8h9i0j1k2l3_extend_rls_coverage.py.
    "ai_interview_responses",
    "payroll_run_tokens",
    # GAP DIKETAHUI, BELUM DIPERBAIKI (lihat plan file): job_portal's
    # _resolve_placement_by_token() punya pola pre-tenant-lookup yang sama
    # tapi `placements` SUDAH RLS-covered sejak migrasi awal -- artinya
    # GET /public/applications/{token} kemungkinan sudah lama gagal di
    # Postgres+RLS aktif. Tidak dikecualikan di sini (placements harus
    # tetap RLS-covered untuk endpoint lain) -- perbaikan ada di sisi
    # service (resolve tanpa filter tenant eksplisit), bukan di skema.
}

# Alembic version table & platform-level table tanpa tenant_id filter
# konsep (dicek terpisah, bukan lewat exclusion list ini).


def _resolve_test_pg_url() -> str | None:
    url = os.environ.get("TEST_POSTGRES_URL")
    if url:
        return url
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql"):
        return db_url
    return None


@pytest.mark.skipif(
    _resolve_test_pg_url() is None,
    reason="Butuh Postgres nyata (TEST_POSTGRES_URL/DATABASE_URL) -- SQLite tidak punya RLS",
)
def test_semua_tabel_tenant_id_notnull_punya_rls_policy():
    # Impor semua models supaya Base.metadata lengkap -- pola sama alembic/env.py.
    import app.core.ai_usage  # noqa: F401
    import app.core.ratelimit  # noqa: F401
    import app.modules.accounting.models  # noqa: F401
    import app.modules.ai.models  # noqa: F401
    import app.modules.ai_interview.models  # noqa: F401
    import app.modules.attendance.models  # noqa: F401
    import app.modules.audit.models  # noqa: F401
    import app.modules.auth.models  # noqa: F401
    import app.modules.blacklist.models  # noqa: F401
    import app.modules.chat.models  # noqa: F401
    import app.modules.clients.models  # noqa: F401
    import app.modules.esign.models  # noqa: F401
    import app.modules.ess.models  # noqa: F401
    import app.modules.finance.models  # noqa: F401
    import app.modules.hrd.models  # noqa: F401
    import app.modules.notifications.models  # noqa: F401
    import app.modules.pages  # noqa: F401
    import app.modules.payroll.models  # noqa: F401
    import app.modules.platform.models  # noqa: F401
    import app.modules.presales.models  # noqa: F401
    import app.modules.rates.models  # noqa: F401
    import app.modules.recruitment.models  # noqa: F401
    import app.modules.talentpool.models  # noqa: F401
    from app.core.database import Base

    tables_with_notnull_tenant = {
        t.name
        for t in Base.metadata.tables.values()
        if "tenant_id" in t.columns and not t.columns["tenant_id"].nullable
    }
    expected_rls = tables_with_notnull_tenant - EXCLUDED_TABLES

    engine = create_engine(_resolve_test_pg_url())
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename FROM pg_policies "
                "WHERE schemaname = 'public' AND policyname = 'tenant_isolation'"
            )
        ).all()
    covered = {r[0] for r in rows}

    missing = expected_rls - covered
    assert not missing, (
        f"Tabel ber-tenant_id NOT NULL tanpa RLS policy: {sorted(missing)}. "
        "Kalau ini tabel baru: tambah ke NEW_BUSINESS_TABLES di migrasi RLS "
        "berikutnya. Kalau sengaja dikecualikan (mis. pre-tenant token "
        "lookup): tambah ke EXCLUDED_TABLES di test ini DENGAN alasan."
    )

    # Peringatan arah lain: entri exclusion yang tabelnya sudah tidak ada
    # sama sekali di skema (bukan yang nullable-nya legit seperti
    # users/audit_logs -- itu memang SENGAJA tidak masuk tables_with_notnull_tenant).
    stale = EXCLUDED_TABLES - set(Base.metadata.tables.keys())
    if stale:
        import warnings

        warnings.warn(
            f"EXCLUDED_TABLES berisi nama yang sudah tidak match skema: {sorted(stale)}",
            stacklevel=1,
        )


@pytest.mark.skipif(
    _resolve_test_pg_url() is None,
    reason="Butuh Postgres nyata (TEST_POSTGRES_URL/DATABASE_URL) -- SQLite tidak punya RLS",
)
def test_tabel_lama_dan_baru_punya_force_row_level_security():
    """FORCE penting: tanpa ini, role PEMILIK tabel tetap melewati RLS-nya
    sendiri walau policy-nya ada. Superuser TETAP selalu melewati RLS
    meski FORCE aktif -- itu sebabnya role runtime app WAJIB non-superuser
    (lihat docker-compose.yml `APP_DB_USER`)."""
    engine = create_engine(_resolve_test_pg_url())
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relrowsecurity AND NOT c.relforcerowsecurity"
            )
        ).all()
    not_forced = {r[0] for r in rows}
    assert not not_forced, (
        f"Tabel dengan RLS enabled tapi TIDAK force: {sorted(not_forced)} -- "
        "RLS tidak berlaku untuk role pemilik tabel tanpa FORCE."
    )
