from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import BPJS_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.bpjs import service
from app.modules.bpjs.schemas import BpjsRecapOut

# Rekap BPJS relevan untuk operasional, HR, dan finance.
router = APIRouter(
    prefix="/bpjs",
    tags=["bpjs"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles(*BPJS_ROLES)),
    ],
)


@router.get("/contributions/{year}/{month}", response_model=BpjsRecapOut)
def monthly_contributions(year: int, month: int, db: Session = Depends(get_db)):
    return service.monthly_recap(db, year, month)


@router.get("/contributions/{year}/{month}/export")
def export_contributions(year: int, month: int, db: Session = Depends(get_db)):
    content, filename = service.contributions_csv(db, year, month)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/enrollments/export")
def export_enrollments(db: Session = Depends(get_db)):
    content, filename = service.enrollments_csv(db)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
