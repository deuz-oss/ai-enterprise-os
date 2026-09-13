from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import PRESALES_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.integrations import service
from app.modules.integrations.schemas import (
    GoogleAuthorizeOut,
    GoogleConnectionStatusOut,
    GoogleSyncResultOut,
)
from app.modules.presales import service as presales_service

# Fase 47 -- sync Gmail/Google Calendar ke Activity lead, per-user
# (koneksi akun Google milik staf sendiri, bukan tenant-wide). Dipisah
# jadi 2 router seperti esign: `router` butuh Bearer auth kita sendiri,
# `public_router` untuk `/callback` yang diakses lewat redirect browser
# dari Google TANPA header Authorization kita (keamanannya ditanggung
# `state` JWT, bukan Bearer token) -- lihat main.py untuk pendaftaran
# tanpa guard lisensi, sama pola `esign_webhook_router`.
router = APIRouter(
    prefix="/integrations/google",
    tags=["integrations"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*PRESALES_ROLES))],
)
public_router = APIRouter(prefix="/integrations/google", tags=["integrations"])


@router.get("/authorize", response_model=GoogleAuthorizeOut)
def authorize(user=Depends(get_current_user)):
    return GoogleAuthorizeOut(authorize_url=service.build_authorize_url(user))


@public_router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    service.handle_callback(db, code=code, state=state)
    frontend_url = get_settings().frontend_base_url
    return RedirectResponse(url=f"{frontend_url}/leads?google_connected=1")


@router.get("/status", response_model=GoogleConnectionStatusOut)
def status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    connection = service.get_status(db, user)
    if connection is None:
        return GoogleConnectionStatusOut(connected=False)
    return GoogleConnectionStatusOut(
        connected=True,
        google_email=connection.google_email,
        last_synced_at=connection.last_synced_at,
    )


@router.delete("/connection", status_code=204)
def disconnect(db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.disconnect(db, user)


@router.post("/sync/{lead_id}", response_model=GoogleSyncResultOut)
def sync_lead(lead_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lead = presales_service.get_lead(db, lead_id)
    return service.sync_lead(db, user=user, lead=lead)
