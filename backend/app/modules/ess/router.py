from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_tenant_user
from app.modules.ess import service
from app.modules.ess.schemas import (
    LeaveCreate,
    LeaveOut,
    MyAttendanceOut,
    MyPayslipOut,
    ProfileOut,
)
from app.modules.hrd.schemas import ContractOut, DocumentOut

# Portal "saya": data selalu milik akun yang sedang login (diselesaikan lewat
# Employee.user_id), jadi tidak perlu require_roles — platform_admin diblokir.
router = APIRouter(
    prefix="/me",
    tags=["selfservice"],
    dependencies=[Depends(get_current_user), Depends(require_tenant_user())],
)


@router.get("/profile", response_model=ProfileOut)
def my_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_own_employee(db, current_user)


@router.get("/contracts", response_model=list[ContractOut])
def my_contracts(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_contracts(db, current_user)


@router.get("/contracts/{contract_id}/download-url")
def my_contract_download_url(
    contract_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"url": service.contract_file_download_url(db, current_user, contract_id)}


@router.get("/documents", response_model=list[DocumentOut])
def my_documents(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_documents(db, current_user)


@router.get("/documents/{document_id}/download-url")
def my_document_download_url(
    document_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"url": service.document_download_url(db, current_user, document_id)}


@router.get("/payslips", response_model=list[MyPayslipOut])
def my_payslips(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_payslips(db, current_user)


@router.get("/attendance", response_model=list[MyAttendanceOut])
def my_attendance(
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_own_attendance(db, current_user, year=year, month=month)


# ---------- Pengajuan cuti/izin ----------


@router.get("/leave-requests", response_model=list[LeaveOut])
def my_leave_requests(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_own_leave_requests(db, current_user)


@router.post("/leave-requests", response_model=LeaveOut, status_code=201)
def request_leave(
    payload: LeaveCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.create_leave_request(db, current_user, payload)


@router.post("/leave-requests/{leave_id}/cancel", response_model=LeaveOut)
def cancel_leave(
    leave_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.cancel_own_leave_request(db, current_user, leave_id)
