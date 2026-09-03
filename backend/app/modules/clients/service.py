from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import assert_not_referenced, parse_uuid
from app.modules import audit
from app.modules.clients.models import Client, DocumentType, LegalDocument
from app.modules.clients.schemas import ClientCreate, ClientUpdate


def _get(db: Session, client_id: str) -> Client:
    client = db.get(Client, parse_uuid(client_id))
    if client is None:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    return client


def create_client(db: Session, payload: ClientCreate) -> Client:
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def list_clients(db: Session, q: str | None = None) -> list[Client]:
    stmt = select(Client).order_by(Client.created_at.desc())
    if q:
        stmt = stmt.where(Client.name.ilike(f"%{q}%"))
    return list(db.execute(stmt).scalars())


def get_client(db: Session, client_id: str) -> Client:
    return _get(db, client_id)


def update_client(db: Session, client_id: str, payload: ClientUpdate) -> Client:
    client = _get(db, client_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client_id: str) -> None:
    client = _get(db, client_id)
    assert_not_referenced(db, "clients", client.id, "Klien")
    db.delete(client)
    db.commit()


def _next_version(db: Session, client_id, document_type: DocumentType) -> int:
    current = db.execute(
        select(func.max(LegalDocument.version)).where(
            LegalDocument.client_id == parse_uuid(client_id),
            LegalDocument.document_type == document_type,
        )
    ).scalar()
    return int(current or 0) + 1


async def upload_document(
    db: Session,
    client_id: str,
    document_type: DocumentType,
    title: str,
    file: UploadFile,
    notes: str | None,
    uploaded_by: str | None,
) -> LegalDocument:
    client = _get(db, client_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    file_name = file.filename or "document.pdf"
    object_key = storage.new_object_key(f"clients/{client.id}", file_name)
    content_type = file.content_type or "application/octet-stream"
    storage.put_object(object_key, data, content_type)

    document = LegalDocument(
        client_id=client.id,
        document_type=document_type,
        title=title or file_name,
        version=_next_version(db, str(client.id), document_type),
        object_key=object_key,
        file_name=file_name,
        mime_type=content_type,
        file_size=len(data),
        notes=notes,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    audit.log_event(
        db,
        action="legal_document.upload",
        entity_type="legal_document",
        entity_id=document.id,
        object_key=object_key,
        detail={"client_id": str(client.id), "file_name": file_name, "version": document.version},
    )
    return document


def list_documents(db: Session, client_id: str) -> list[LegalDocument]:
    client = _get(db, client_id)
    return list(client.documents)


def download_url(db: Session, document_id: str) -> str:
    document = db.get(LegalDocument, parse_uuid(document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    audit.log_event(
        db,
        action="legal_document.download_url",
        entity_type="legal_document",
        entity_id=document.id,
        object_key=document.object_key,
        detail={"client_id": str(document.client_id), "file_name": document.file_name},
    )
    return storage.presigned_get_url(document.object_key)


def expiring_contracts(db: Session, within_days: int) -> list[Client]:
    from datetime import date, timedelta

    limit = date.today() + timedelta(days=within_days)
    stmt = (
        select(Client)
        .where(Client.contract_end.is_not(None))
        .where(Client.contract_end <= limit)
        .where(Client.status == "aktif")
        .order_by(Client.contract_end)
    )
    return list(db.execute(stmt).scalars())
