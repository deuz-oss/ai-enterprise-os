from collections.abc import Generator
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Pastikan folder data lokal ada sebelum engine dibuat (SQLite membuat file,
# tetapi tidak membuat foldernya).
settings.data_root.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.effective_database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def parse_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def referencing_row_counts(db: Session, table_name: str, row_id: Any) -> dict[str, int]:
    """Hitung baris di tabel LAIN yang masih mereferensikan `row_id` lewat FK
    ke `table_name`, ditemukan otomatis dari `Base.metadata` (bukan daftar
    manual per model) -- supaya tabel baru yang menambah FK ke entitas induk
    ini OTOMATIS ikut ter-cover tanpa perlu sentuh kode ini lagi.

    Dipakai sebagai guard sebelum `db.delete(...)` untuk entitas yang tidak
    punya `ondelete` cascade di skema (sengaja -- lihat audit 2026-09-02,
    cascade DB dianggap terlalu berbahaya untuk data bisnis). Tanpa guard
    ini, delete akan gagal dengan IntegrityError 500 mentah alih-alih pesan
    yang bisa ditindaklanjuti user."""
    from sqlalchemy import func, select

    counts: dict[str, int] = {}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name != table_name:
                continue
            col = fk.parent
            n = db.scalar(select(func.count()).select_from(table).where(col == row_id))
            if n:
                counts[table.name] = n
    return counts


def assert_not_referenced(db: Session, table_name: str, row_id: Any, entity_label: str) -> None:
    """Lempar 422 dengan pesan jelas kalau `row_id` masih direferensikan
    tabel lain -- pola pakai: panggil ini tepat sebelum `db.delete(obj)`."""
    from fastapi import HTTPException

    counts = referencing_row_counts(db, table_name, row_id)
    if not counts:
        return
    detail = ", ".join(f"{n} {t}" for t, n in sorted(counts.items()))
    raise HTTPException(
        status_code=422,
        detail=(
            f"{entity_label} ini masih direferensikan data lain ({detail}) -- "
            "tidak bisa dihapus. Arsipkan/nonaktifkan, atau hapus data terkait dulu."
        ),
    )
