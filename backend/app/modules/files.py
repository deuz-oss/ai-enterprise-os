"""Endpoint unduh file untuk mode penyimpanan lokal.

Hanya aktif saat MinIO/S3 tidak dikonfigurasi. URL memuat UUID acak
(capability URL, setara presigned URL S3) sehingga tidak perlu header JWT
saat dibuka dari browser.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{object_key:path}")
def download_local_file(object_key: str):
    settings = get_settings()
    if settings.storage_configured:
        raise HTTPException(status_code=404, detail="Mode storage S3/MinIO aktif")
    root = settings.uploads_root.resolve()
    target = (root / object_key).resolve()
    # is_relative_to (bukan str.startswith): "uploads-lain/x" juga diawali
    # string "uploads" sehingga lolos cek prefiks lama -> baca folder saudara.
    if not target.is_relative_to(root):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    # Mode storage lokal (dev): tanpa cache juga, samakan perilaku dgn
    # presigned URL S3 untuk data sensitif (lihat storage.presigned_get_url).
    return FileResponse(target, filename=target.name, headers={"Cache-Control": "no-store"})
