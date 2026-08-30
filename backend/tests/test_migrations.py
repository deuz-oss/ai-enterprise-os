"""Test migrasi Alembic: `upgrade head` menghasilkan skema identik dengan metadata.

Menjamin file migrasi tidak pernah tertinggal saat model berubah:
jika ada tabel di Base.metadata yang belum ada di migrasi, test ini gagal.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.database import Base
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _sqlite_url(db_path: Path) -> str:
    return "sqlite:///" + db_path.as_posix()


def test_upgrade_head_identik_dengan_create_all(tmp_path):
    db_path = tmp_path / "migration.db"
    url = _sqlite_url(db_path)
    engine = create_engine(url)
    try:
        command.upgrade(_alembic_config(url), "head")

        insp = inspect(engine)
        migrated = set(insp.get_table_names()) - {"alembic_version"}
        expected = set(Base.metadata.tables.keys())
        assert migrated == expected, (
            f"Tabel hilang dari migrasi: {expected - migrated or '-'}; "
            f"Tabel asing: {migrated - expected or '-'}"
        )

        # Kolom per tabel juga harus sama (nama + tipe utama)
        for table_name in expected:
            mig_cols = {c["name"] for c in insp.get_columns(table_name)}
            meta_cols = set(Base.metadata.tables[table_name].columns.keys())
            assert mig_cols == meta_cols, f"Kolom beda di tabel {table_name}"
    finally:
        engine.dispose()


def test_downgrade_base_mengosongkan_skema(tmp_path):
    db_path = tmp_path / "downgrade.db"
    url = _sqlite_url(db_path)
    engine = create_engine(url)
    try:
        command.upgrade(_alembic_config(url), "head")
        command.downgrade(_alembic_config(url), "base")

        insp = inspect(engine)
        sisa = set(insp.get_table_names()) - {"alembic_version"}
        assert sisa == set(), f"Sisa tabel setelah downgrade: {sisa}"
    finally:
        engine.dispose()


def test_seeded_rows_readable_via_orm(tmp_path):
    """Data hasil backfill migrasi (raw SQL) harus bisa dibaca balik lewat ORM.

    Regresi: migrasi lama menyisipkan status enum via literal SQL memakai
    .value Python ('aktif') alih-alih .name yang sebenarnya dipakai
    SQLAlchemy Enum(PyEnumClass, native_enum=False) secara default ('active')
    — cocok secara struktur/kolom (makanya lolos test upgrade di atas) tapi
    meledak saat baris benar-benar dibaca lewat model ORM. Postgres asli via
    docker-compose menemukan ini; SQLite tidak — repro di sini biar tertangkap
    otomatis tanpa perlu docker.
    """
    from app.modules.platform.models import Tenant, TenantAppLicense
    from sqlalchemy.orm import Session

    db_path = tmp_path / "seeded.db"
    url = _sqlite_url(db_path)
    engine = create_engine(url)
    try:
        command.upgrade(_alembic_config(url), "head")
        with Session(engine) as session:
            tenant = session.query(Tenant).filter_by(slug="default").one()
            assert tenant.status.name == "active"

            licenses = session.query(TenantAppLicense).filter_by(tenant_id=tenant.id).all()
            assert len(licenses) > 0
            assert all(lic.status.name == "active" for lic in licenses)
    finally:
        engine.dispose()
