"""Baca unggahan CSV secara aman untuk semua endpoint impor.

Dulu tiap impor memanggil `raw.decode("utf-8-sig")` langsung: CSV yang
disimpan Excel Windows (cp1252) melempar UnicodeDecodeError -> HTTP 500,
dan ukuran file tidak dibatasi sama sekali.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

MAX_CSV_BYTES = 5 * 1024 * 1024


async def read_csv_text(file: UploadFile) -> str:
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran CSV maksimal 5 MB")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Fallback Excel Windows. cp1252 tidak mendefinisikan 5 byte
        # (0x81, 0x8D, ...) -> file biner/rusak tetap ditolak rapi.
        try:
            return raw.decode("cp1252")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=422, detail="File bukan CSV teks (simpan sebagai CSV UTF-8)"
            ) from None
