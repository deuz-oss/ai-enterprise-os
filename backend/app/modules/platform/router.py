from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_platform_admin
from app.modules.platform import service
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
