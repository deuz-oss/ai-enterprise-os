"""Jalankan migrasi Alembic secara aman untuk container.

Logika:
- alembic_version sudah ada  -> `upgrade head` (jalur normal)
- DB berisi tabel tapi belum pernah di-stamp (dibuat via create_all lama)
  -> `stamp head` dulu, baru `upgrade head` (skema create_all selalu
     mengikuti head pada repo yang sama, jadi penandaan ini aman)
- DB kosong                  -> `upgrade head` biasa

Dipanggil entrypoint backend sebelum uvicorn agar setiap start memastikan
skema mutakhir tanpa pernah menabrak tabel yang sudah ada.
"""

from __future__ import annotations

import sys

from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from sqlalchemy import create_engine, inspect


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.effective_database_url)
    try:
        insp = inspect(engine)
        stamped = insp.has_table("alembic_version")
        has_data = insp.has_table("users")

        cfg = Config("alembic.ini")
        if not stamped and has_data:
            print("[migrate] DB lama tanpa alembic_version -> stamp head", flush=True)
            command.stamp(cfg, "head")
        command.upgrade(cfg, "head")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
