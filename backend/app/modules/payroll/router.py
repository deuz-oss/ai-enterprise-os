from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.modules.payroll import service
from app.modules.payroll.schemas import (
    AttendanceOut,
    AttendanceUpsert,
    GenerateSlipsRequest,
    PayslipOut,
    RunCreate,
    RunOut,
    TaxPreviewIn,
)

router = APIRouter(
    prefix="/payroll",
    tags=["payroll"],
    dependencies=[Depends(get_current_user), Depends(require_roles("operations", "management"))],
)


# ---------- Absensi & approval klien ----------


@router.get("/attendance", response_model=list[AttendanceOut])
def list_attendance(
    year: int = Query(...), month: int = Query(...), db: Session = Depends(get_db)
):
    return service.list_attendance(db, year=year, month=month)


@router.post("/attendance", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def upsert_attendance(payload: AttendanceUpsert, db: Session = Depends(get_db)):
    return service.upsert_attendance(db, payload)


@router.patch("/attendance/{attendance_id}/client-approval", response_model=AttendanceOut)
def set_client_approval(
    attendance_id: str, approved: bool = Query(True), db: Session = Depends(get_db)
):
    """Approval kehadiran/lembur oleh klien sebelum masuk payrol."""
    return service.set_client_approval(db, attendance_id, approved)


# ---------- Payroll runs & slip gaji ----------


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)):
    return service.list_runs(db)


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    return service.create_run(db, payload)


@router.post("/runs/{run_id}/generate", response_model=list[PayslipOut], status_code=201)
def generate_slips(run_id: str, payload: GenerateSlipsRequest, db: Session = Depends(get_db)):
    return service.generate_slips(db, run_id, payload)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return service.get_run(db, run_id)


@router.get("/runs/{run_id}/slips", response_model=list[PayslipOut])
def list_slips(run_id: str, db: Session = Depends(get_db)):
    return service.list_slips(db, run_id)


@router.post("/runs/{run_id}/finalize", response_model=RunOut)
def finalize_run(run_id: str, db: Session = Depends(get_db)):
    return service.finalize_run(db, run_id)


# ---------- Preview PPh 21 ----------


@router.post("/tax-preview")
def tax_preview(payload: TaxPreviewIn, db: Session = Depends(get_db)):
    return service.preview_tax(payload)
