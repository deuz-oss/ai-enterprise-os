"""Utilitas ekstraksi teks dokumen (CV, kontrak) untuk diproses AI."""

from __future__ import annotations

from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfReader

# Batas karakter dokumen yang dikirim/diindeks agar prompt tetap wajar.
MAX_DOC_CHARS = 24_000


def extract_document_text(data: bytes, file_name: str) -> str:
    """Ekstrak teks dari dokumen (PDF via pypdf; selain itu dibaca sebagai teks)."""
    if file_name.lower().endswith(".pdf") or data[:5] == b"%PDF-":
        try:
            reader = PdfReader(BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # noqa: BLE001 - pypdf melempar error umum
            raise HTTPException(
                status_code=422, detail="Dokumen PDF gagal dibaca; pastikan file tidak rusak"
            ) from exc
    else:
        text = data.decode("utf-8", errors="replace")
    if len(text.strip()) < 40:
        raise HTTPException(
            status_code=422,
            detail="Isi dokumen tidak terbaca. Gunakan PDF berbasis teks atau file .txt",
        )
    return text[:MAX_DOC_CHARS]
