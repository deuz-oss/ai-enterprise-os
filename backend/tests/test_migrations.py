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
