from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import CLIENTS_ROLES
from app.core.ratelimit import get_limiter
from app.core.security import get_current_user, require_roles
from app.core.tenancy import get_request_meta
from app.modules.clients import service
from app.modules.clients.models import DocumentType
from app.modules.clients.schemas import (
    ClientCreate,
    ClientOut,
    ClientPortalAccessOut,
    ClientSiteCreate,
    ClientSiteOut,
    ClientSiteUpdate,
    ClientSiteWithClientOut,
    ClientUpdate,
    DocumentOut,
)

router = APIRouter(
    prefix="/clients",
    tags=["clients"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*CLIENTS_ROLES))],
)


@router.get("", response_model=list[ClientOut])
def list_clients(q: str | None = Query(None, max_length=100), db: Session = Depends(get_db)):
    return service.list_clients(db, q=q)


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    return service.create_client(db, payload)


@router.get("/expiring-contracts", response_model=list[ClientOut])
def expiring_contracts(within_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return service.expiring_contracts(db, within_days)


# Wajib didaftarkan sebelum `/{client_id}` -- "sites" segmen tunggal akan
# ketangkap sebagai client_id kalau route ini di bawah.
@router.get("/sites", response_model=list[ClientSiteWithClientOut])
def list_all_sites(db: Session = Depends(get_db)):
    """Lintas klien -- dropdown pemilihan lokasi geofencing di halaman Karyawan."""
    return [
        ClientSiteWithClientOut(
            id=site.id,
            client_id=site.client_id,
            name=site.name,
            address=site.address,
            latitude=site.latitude,
            longitude=site.longitude,
            radius_meters=site.radius_meters,
            created_at=site.created_at,
            client_name=client_name,
        )
        for site, client_name in service.list_all_sites(db)
    ]


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


# ---------- Portal monitoring klien (link ber-token, tanpa akun) ----------


@router.get("/{client_id}/portal-access", response_model=ClientPortalAccessOut | None)
def portal_access_status(client_id: str, db: Session = Depends(get_db)):
    return service.get_portal_access_status(db, client_id)


@router.post("/{client_id}/portal-access")
def create_portal_access(
    client_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """Buat/ganti link portal klien -- token mentah cuma muncul di response ini."""
    access, raw = service.generate_portal_access(db, current_user, client_id)
    return {
        "access": ClientPortalAccessOut.model_validate(access),
        "url": f"/clients/portal/{raw}",
    }


@router.delete("/{client_id}/portal-access", status_code=204)
def delete_portal_access(client_id: str, db: Session = Depends(get_db)):
    service.revoke_portal_access(db, client_id)


# ---------- Lokasi kantor klien (geofencing absensi, Fase 34) ----------


@router.post("/{client_id}/sites", response_model=ClientSiteOut, status_code=201)
def create_site(client_id: str, payload: ClientSiteCreate, db: Session = Depends(get_db)):
    return service.create_site(db, client_id, payload)


@router.get("/{client_id}/sites", response_model=list[ClientSiteOut])
def list_sites(client_id: str, db: Session = Depends(get_db)):
    return service.list_sites(db, client_id)


@router.patch("/sites/{site_id}", response_model=ClientSiteOut)
def update_site(site_id: str, payload: ClientSiteUpdate, db: Session = Depends(get_db)):
    return service.update_site(db, site_id, payload)


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: str, db: Session = Depends(get_db)):
    service.delete_site(db, site_id)


# ---------- Publik (tanpa akun): monitoring klien via link ber-token ----------
# Guard lisensi/tenant TIDAK berlaku di sini -- akses dikontrol token, data
# read-only, dan setiap kunjungan tercatat (`last_accessed_at`).

public_router = APIRouter(prefix="/clients/portal", tags=["clients-portal"])

_CLIENT_PORTAL_RATE_MAX = 30
_CLIENT_PORTAL_RATE_WINDOW_SEC = 3600


def _check_portal_rate_limit(db: Session) -> None:
    ip, _ = get_request_meta()
    limiter = get_limiter("client_portal_token")
    key = ip or "unknown"
    allowed, retry_after = limiter.check(
        db, key, max_attempts=_CLIENT_PORTAL_RATE_MAX, window_seconds=_CLIENT_PORTAL_RATE_WINDOW_SEC
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan dari lokasi ini. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after)},
        )
    limiter.hit(db, key, window_seconds=_CLIENT_PORTAL_RATE_WINDOW_SEC)


@public_router.get("/{token}")
def client_portal_view(
    token: str,
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Rekap kehadiran & lembur read-only untuk klien (tanpa akun)."""
    _check_portal_rate_limit(db)
    return service.client_portal_attendance(db, token, year, month)
