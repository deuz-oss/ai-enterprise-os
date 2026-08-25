from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.apps import APP_REGISTRY
from app.core.database import get_db
from app.core.security import get_current_user, require_platform_admin
from app.modules.apps.schemas import LicenseSetIn
from app.modules.platform import service
from app.modules.platform.models import LicenseStatus, TenantAppLicense
from app.modules.platform.schemas import (
    TenantCreate,
    TenantOut,
    TenantProvisionedOut,
    TenantUpdate,
)

# Khusus platform_admin: mengelola daftar tenant SaaS.
# Guard khusus tanpa bypass "admin" agar admin tenant tidak ikut lolos.
router = APIRouter(
    prefix="/platform",
    tags=["platform"],
    dependencies=[Depends(get_current_user), Depends(require_platform_admin())],
)


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return service.list_tenants(db)


@router.post("/tenants", response_model=TenantProvisionedOut, status_code=201)
def provision_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    return service.provision_tenant(db, payload)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: UUID, payload: TenantUpdate, db: Session = Depends(get_db)):
    return service.update_tenant(db, tenant_id, payload)


# ---------- Lisensi aplikasi per tenant ----------


@router.get("/tenants/{tenant_id}/licenses")
def list_licenses(tenant_id: UUID, db: Session = Depends(get_db)):
    service._get_tenant(db, tenant_id)
    rows = {row.app_key: row for row in service.list_tenant_licenses(db, tenant_id)}
    result = []
    for key, spec in APP_REGISTRY.items():
        row: TenantAppLicense | None = rows.get(key)
        result.append(
            {
                "app_key": key,
                "name": spec.name,
                "status": row.status.value if row else None,
                "expires_at": row.expires_at if row else None,
            }
        )
    return result


@router.patch("/tenants/{tenant_id}/licenses/{app_key}")
def set_license(
    tenant_id: UUID,
    app_key: str,
    payload: LicenseSetIn,
    db: Session = Depends(get_db),
):
    """Aktifkan/perpanjang/cabut lisensi aplikasi satu tenant."""
    try:
        status_enum = LicenseStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Status tidak valid; gunakan {', '.join(s.value for s in LicenseStatus)}",
        ) from None
    row = service.set_license_status(db, tenant_id, app_key, status_enum, payload.expires_at)
    return {
        "app_key": row.app_key,
        "status": row.status.value,
        "expires_at": row.expires_at,
    }
