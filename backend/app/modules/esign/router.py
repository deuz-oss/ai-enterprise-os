from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import ESIGN_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.esign import service
from app.modules.esign.schemas import (
    EsignConfigOut,
    EsignRequestOut,
    EsignSendIn,
)

# Pengelolaan TTE kontrak → domain HR.
router = APIRouter(
    prefix="/esign",
    tags=["esign"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*ESIGN_ROLES))],
)

# Webhook dipanggil penyedia TTE tanpa JWT → router terpisah tanpa guard auth.
# Keaslian peserta diverifikasi lewat header X-Esign-Signature (HMAC).
webhook_router = APIRouter(prefix="/esign", tags=["esign"])


@router.get("/config", response_model=EsignConfigOut)
def config():
    return service.esign_config()


@router.post("/contracts/{contract_id}/send", response_model=EsignRequestOut)
def send_contract(contract_id: UUID, payload: EsignSendIn, db: Session = Depends(get_db)):
    return service.send_contract(db, contract_id, payload.signer_name, payload.signer_email)


@router.get("/requests", response_model=list[EsignRequestOut])
def list_requests(
    contract_id: UUID | None = None,
    placement_id: UUID | None = None,
    agreement_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    return service.list_requests(db, contract_id, placement_id, agreement_id)


@router.post("/requests/{request_id}/refresh", response_model=EsignRequestOut)
def refresh_status(request_id: UUID, db: Session = Depends(get_db)):
    """Tarik status terbaru dari penyedia (polling manual)."""
    return service.refresh_status(db, request_id)


@router.post("/requests/{request_id}/simulate-complete", response_model=EsignRequestOut)
def simulate_complete(request_id: UUID, db: Session = Depends(get_db)):
    """Hanya mode sandbox — simulasi webhook selesai untuk demo/test."""
    return service.simulate_completion(db, request_id)


@webhook_router.post("/webhook", response_model=EsignRequestOut)
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    return service.handle_webhook(db, request, body)
