"""Abstraksi object storage dengan dua mode:

1. **MinIO/S3** — dipakai saat STORAGE_* env terisi (mis. Docker Compose).
2. **Lokal** — fallback tanpa konfigurasi: file ditulis ke `<data_dir>/uploads/`
   dan diunduh lewat endpoint `/api/v1/files/{object_key}`.

Mode lokal memakai capability URL (nama file memuat UUID acak), setara dengan
model presigned URL S3. Untuk production, gunakan MinIO/S3.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _client():
    settings = get_settings()
    if not settings.storage_configured:
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        config=BotoConfig(signature_version="s3v4"),
    )


def _bucket() -> str:
    return get_settings().storage_bucket


def ensure_storage() -> None:
    client = _client()
    if client is None:
        get_settings().uploads_root.mkdir(parents=True, exist_ok=True)
        logger.info("Storage lokal aktif di %s", get_settings().uploads_root.resolve())
        return
    bucket = _bucket()
    try:
        client.head_bucket(Bucket=bucket)
    except (ClientError, BotoCoreError):
        try:
            client.create_bucket(Bucket=bucket)
        except (ClientError, BotoCoreError) as exc:  # pragma: no cover - infra dependent
            logger.error("Cannot create bucket %s: %s", bucket, exc)


def new_object_key(prefix: str, file_name: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y/%m/%d")
    safe_name = file_name.replace("\\", "_").replace("/", "_")
    # Multi-tenant: file di-namespace per tenant bila konteks tersedia.
    tenant_part = ""
    from app.core.tenancy import get_tenant

    if get_tenant() is not None:
        tenant_part = f"tenants/{get_tenant()}/"
    return f"{tenant_part}{prefix}/{stamp}/{uuid4().hex}-{safe_name}"


def put_object(object_key: str, data: bytes, content_type: str) -> str:
    client = _client()
    if client is None:
        path = get_settings().uploads_root / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return object_key
    try:
        client.put_object(
            Bucket=_bucket(), Key=object_key, Body=data, ContentType=content_type
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("put_object failed: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal menyimpan file ke storage") from exc
    return object_key


def get_object(object_key: str) -> bytes:
    """Baca kembali isi objek (mis. CV/ dokumen untuk diproses AI)."""
    client = _client()
    if client is None:
        path = get_settings().uploads_root / object_key
        try:
            return path.read_bytes()
        except OSError as exc:
            logger.error("get_object lokal gagal: %s", exc)
            raise HTTPException(status_code=404, detail="File tidak ditemukan di storage") from exc
    try:
        resp = client.get_object(Bucket=_bucket(), Key=object_key)
        body: bytes = resp["Body"].read()
        return body
    except (ClientError, BotoCoreError) as exc:
        logger.error("get_object failed: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal membaca file dari storage") from exc


def presigned_get_url(object_key: str, expires_seconds: int = 3600) -> str:
    client = _client()
    if client is None:
        return f"/api/v1/files/{quote(object_key, safe='/')}"
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": _bucket(), "Key": object_key},
            ExpiresIn=expires_seconds,
        )
    except (ClientError, BotoCoreError) as exc:
        raise HTTPException(status_code=502, detail="Gagal membuat link unduhan") from exc
