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
