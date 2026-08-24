"""Layanan tanda tangan elektronik untuk kontrak kerja.

Alur: kontrak yang sudah punya file dikirim ke penyedia TTE (adapter),
status dilacak di tabel esign_requests. Webhook dari penyedia (atau
simulasi sandbox) menandai selesai dan otomatis memperbarui status TTD
kontrak terkait.
"""

from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.esign.base import EsignAdapter
from app.core.esign.privy import PrivyAdapter
from app.core.esign.sandbox import SandboxAdapter
from app.core.storage import get_object
from app.modules.esign.models import EsignRequest, EsignStatus
from app.modules.esign.schemas import EsignConfigOut
from app.modules.hrd.models import ContractSignStatus, EmploymentContract

_STATUS_TO_MODEL = {
    "pending": EsignStatus.sent,
    "viewed": EsignStatus.viewed,
    "completed": EsignStatus.completed,
    "declined": EsignStatus.declined,
    "expired": EsignStatus.expired,
}


def get_adapter() -> EsignAdapter:
    settings = get_settings()
    if settings.esign_provider == "sandbox":
        return SandboxAdapter()
    if settings.esign_provider == "privy":
        return PrivyAdapter()
    raise HTTPException(
        status_code=503,
        detail="Integrasi TTE belum aktif. Set ESIGN_PROVIDER (sandbox/privy) di .env.",
    )


def esign_config() -> EsignConfigOut:
    settings = get_settings()
    return EsignConfigOut(
        provider=settings.esign_provider or None,
        webhook_ready=bool(settings.esign_webhook_secret),
    )


def _get_contract(db: Session, contract_id: UUID) -> EmploymentContract:
    contract = db.get(EmploymentContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Kontrak tidak ditemukan")
    return contract


def send_contract(
    db: Session,
    contract_id: UUID,
    signer_name: str,
    signer_email: str,
) -> EsignRequest:
    """Kirim file kontrak ke penyedia TTE untuk ditandatangani."""
    contract = _get_contract(db, contract_id)
    if not contract.object_key:
        raise HTTPException(
            status_code=422, detail="Kontrak belum memiliki file untuk ditandatangani"
        )
    pending = db.scalars(
        select(EsignRequest)
        .where(EsignRequest.contract_id == contract.id)
        .where(EsignRequest.status.in_([EsignStatus.sent, EsignStatus.viewed]))
        .limit(1)
    ).first()
    if pending:
        raise HTTPException(
            status_code=409,
            detail="Masih ada permintaan TTE yang berjalan untuk kontrak ini",
        )

    pdf_bytes = get_object(contract.object_key)
    result = get_adapter().send_document(
        pdf_bytes=pdf_bytes,
        file_name=contract.file_name or f"{contract.contract_no}.pdf",
        title=contract.contract_no,
        signer_name=signer_name,
        signer_email=signer_email,
    )
    request = EsignRequest(
        contract_id=contract.id,
        provider=get_settings().esign_provider,
        provider_document_id=result.provider_document_id,
        signer_name=signer_name,
        signer_email=signer_email,
        sign_url=result.sign_url,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_requests(db: Session, contract_id: UUID | None = None) -> list[EsignRequest]:
    stmt = select(EsignRequest).order_by(EsignRequest.created_at.desc())
    if contract_id:
        _get_contract(db, contract_id)
        stmt = stmt.where(EsignRequest.contract_id == contract_id)
    return list(db.scalars(stmt).all())


def _signature_of(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, "sha256").hexdigest()


def _verify_webhook_secret(request: Request, body: bytes) -> None:
    secret = get_settings().esign_webhook_secret
    provided = request.headers.get("X-Esign-Signature") or ""
    if not secret or not hmac.compare_digest(provided, _signature_of(body, secret)):
        raise HTTPException(status_code=401, detail="Tanda tangan webhook tidak valid")


def handle_webhook(db: Session, request: Request, body: bytes) -> EsignRequest:
    """Terima callback penyedia: perbarui status permintaan & kontrak."""
    _verify_webhook_secret(request, body)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Body webhook bukan JSON valid") from exc
    doc_id = str(payload.get("document_token") or payload.get("document_id") or "").strip()
    vendor_status = str(payload.get("status") or "").lower()
    if not doc_id:
        raise HTTPException(status_code=422, detail="Webhook tanpa identitas dokumen")

    esign_request = db.scalars(
        select(EsignRequest).where(EsignRequest.provider_document_id == doc_id).limit(1)
    ).first()
    if not esign_request:
        raise HTTPException(status_code=404, detail="Permintaan TTE tidak ditemukan")

    mapped = _STATUS_TO_MODEL.get(vendor_status, EsignStatus.failed)
    return _apply_status(db, esign_request, mapped, raw=payload)


def simulate_completion(db: Session, request_id: UUID) -> EsignRequest:
    """Sandbox saja: tandai permintaan selesai seolah webhook datang."""
    if get_settings().esign_provider != "sandbox":
        raise HTTPException(status_code=404, detail="Endpoint hanya tersedia di mode sandbox")
    esign_request = db.get(EsignRequest, request_id)
    if not esign_request:
        raise HTTPException(status_code=404, detail="Permintaan TTE tidak ditemukan")
    return _apply_status(
        db,
        esign_request,
        EsignStatus.completed,
        raw={"provider": "sandbox", "simulated": True},
    )


def refresh_status(db: Session, request_id: UUID) -> EsignRequest:
    """Tarik status terbaru dari penyedia (polling manual oleh user HR)."""
    esign_request = db.get(EsignRequest, request_id)
    if not esign_request:
        raise HTTPException(status_code=404, detail="Permintaan TTE tidak ditemukan")
    if esign_request.status == EsignStatus.completed:
        return esign_request
    provider_status = get_adapter().get_status(esign_request.provider_document_id)
    mapped = _STATUS_TO_MODEL.get(provider_status.status, EsignStatus.sent)
    return _apply_status(db, esign_request, mapped, raw=provider_status.raw)


def _apply_status(
    db: Session,
    esign_request: EsignRequest,
    status: EsignStatus,
    *,
    raw: dict | None,
) -> EsignRequest:
    esign_request.status = status
    esign_request.detail_json = json.dumps(raw, ensure_ascii=False) if raw else None
    if status == EsignStatus.completed and not esign_request.signed_at:
        esign_request.signed_at = datetime.now(UTC)
        # Efek samping: kontrak resmi tercatat ditandatangani.
        contract = db.get(EmploymentContract, esign_request.contract_id)
        if contract:
            contract.sign_status = ContractSignStatus.signed
            contract.signed_at = esign_request.signed_at
    elif status in (EsignStatus.declined, EsignStatus.expired):
        esign_request.error = f"Dokumen {status.value} oleh penandatangan"
    db.commit()
    db.refresh(esign_request)
    return esign_request
