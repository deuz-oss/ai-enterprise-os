"""Aset portofolio & lisensi (Fase 7): endpoint untuk semua akun bertenanta."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.apps import APP_REGISTRY
from app.core.database import get_db
from app.core.permissions import APPS_TRIAL_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.apps.schemas import AppEntitlementOut, TrialActivatedOut
from app.modules.platform.models import TenantAppLicense
from app.modules.platform.service import activate_trial, is_licensed

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("", response_model=list[AppEntitlementOut])
def list_apps(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Daftar aplikasi + status lisensi tenant — sumber nav dinamis & launcher."""
    rows: dict[str, TenantAppLicense] = {}
    if current_user.tenant_id is not None:
        for lic in db.execute(
            select(TenantAppLicense).where(TenantAppLicense.tenant_id == current_user.tenant_id)
        ).scalars():
            rows[lic.app_key] = lic
    result: list[AppEntitlementOut] = []
    for spec in APP_REGISTRY.values():
        row: TenantAppLicense | None = rows.get(spec.key)
        result.append(
            AppEntitlementOut(
                key=spec.key,
                name=spec.name,
                emoji=spec.emoji,
                accent=spec.accent,
                description=spec.description,
                depends_on=list(spec.depends_on),
                licensed=is_licensed(db, current_user.tenant_id, spec.key),
                status=row.status.value if row else None,
                expires_at=row.expires_at if row else None,
            )
        )
    return result


@router.post("/{app_key}/trial", response_model=TrialActivatedOut)
def start_trial(
    app_key: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    _manager=Depends(require_roles(*APPS_TRIAL_ROLES)),
):
    """Aktivasi trial mandiri 14 hari; sekali per aplikasi per tenant."""
    license_row = activate_trial(db, current_user.tenant_id, app_key)
    return TrialActivatedOut(
        app_key=license_row.app_key,
        status=license_row.status.value,
        expires_at=license_row.expires_at,
    )
