from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.modules.clients import service
from app.modules.clients.models import DocumentType
from app.modules.clients.schemas import ClientCreate, ClientOut, ClientUpdate, DocumentOut

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ClientOut])
def list_clients(q: str | None = Query(None, max_length=100), db: Session = Depends(get_db)):
    return service.list_clients(db, q=q)


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    return service.create_client(db, payload)


@router.get("/expiring-contracts", response_model=list[ClientOut])
def expiring_contracts(
    within_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)
):
    return service.expiring_contracts(db, within_days)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)):
    return service.get_client(db, client_id)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: str, payload: ClientUpdate, db: Session = Depends(get_db)):
    return service.update_client(db, client_id, payload)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str, db: Session = Depends(get_db)):
    service.delete_client(db, client_id)


@router.post("/{client_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    client_id: str,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.other),
    title: str = Form(""),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await service.upload_document(
        db,
        client_id,
        document_type,
        title,
        file,
        notes,
        current_user.id,
    )


@router.get("/{client_id}/documents", response_model=list[DocumentOut])
def list_documents(client_id: str, db: Session = Depends(get_db)):
    return service.list_documents(db, client_id)


@router.get("/documents/{document_id}/download-url")
def download_url(document_id: str, db: Session = Depends(get_db)):
    return {"url": service.download_url(db, document_id)}
