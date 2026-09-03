from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import HRD_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.ess import service as ess_service
from app.modules.ess.models import LeaveStatus
from app.modules.ess.schemas import (
    AttendanceCorrectionOut,
    LeaveBalanceOut,
    LeaveBalanceUpsertIn,
    LeaveDecisionIn,
    LeaveOut,
    SelfserviceAccountOut,
)
from app.modules.hrd import service
from app.modules.hrd.models import EmployeeStatus, HrDocumentType
from app.modules.hrd.schemas import (
    ContractCreate,
    ContractOut,
    ContractUpdate,
    DocumentOut,
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    InsuranceCreate,
    InsuranceOut,
    InsuranceUpdate,
    OnboardCreate,
)

router = APIRouter(
    prefix="/employees",
    tags=["hrd"],
    dependencies=[Depends(get_current_user), Depends(require_roles(*HRD_ROLES))],
)


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    response: Response,
    q: str | None = Query(None, max_length=100),
    status_filter: EmployeeStatus | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = service.list_employees(db, q=q, status=status_filter, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    return service.create_employee(db, payload)


@router.post("/onboard", response_model=EmployeeOut, status_code=201)
def onboard_employee(payload: OnboardCreate, db: Session = Depends(get_db)):
    """Angkat kandidat hasil placement menjadi karyawan aktif."""
    return service.onboard_from_placement(db, payload)


# ---------- Portal self-service: akun & cuti (statis, sebelum /{employee_id}) ----------


@router.get("/selfservice-accounts", response_model=list[SelfserviceAccountOut])
def selfservice_accounts(db: Session = Depends(get_db)):
    """Akun role karyawan yang belum tertaut — kandidat untuk diaktifkan."""
    return ess_service.list_selfservice_accounts(db)


@router.get("/leave-requests", response_model=list[LeaveOut])
def list_leave_requests(
    status_filter: LeaveStatus | None = Query(None, alias="status"),
    employee_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return ess_service.hr_list_leave_requests(
        db, status_filter=status_filter, employee_id=employee_id
    )


@router.get("/reports/leave")
def export_leave_csv(year: int | None = Query(None), db: Session = Depends(get_db)):
    """CSV rekap pengajuan cuti/izin satu tahun (default tahun berjalan)."""
    content, filename = ess_service.leave_recap_csv(db, year)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/attendance")
def export_attendance_csv(
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """CSV rekap kehadiran/lembur; tanpa filter = seluruh periode."""
    content, filename = ess_service.attendance_recap_csv(db, year=year, month=month)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/leave-requests/{leave_id}/decision", response_model=LeaveOut)
def decide_leave_request(
    leave_id: str,
    payload: LeaveDecisionIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Setujui/tolak pengajuan cuti-izin karyawan (wajib status menunggu)."""
    return ess_service.decide_leave_request(
        db, current_user, leave_id, payload.approved, payload.note
    )


@router.get("/leave-requests/{leave_id}/attachment/download-url")
def leave_attachment_url(leave_id: str, db: Session = Depends(get_db)):
    return {"url": ess_service.hr_attachment_download_url(db, leave_id)}


@router.get("/attendance-corrections", response_model=list[AttendanceCorrectionOut])
def list_attendance_corrections(
    status_filter: LeaveStatus | None = Query(None, alias="status"),
    employee_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Daftar pengajuan koreksi absensi dari portal karyawan."""
    return ess_service.hr_list_attendance_corrections(
        db, status_filter=status_filter, employee_id=employee_id
    )


@router.patch(
    "/attendance-corrections/{correction_id}/decision",
    response_model=AttendanceCorrectionOut,
)
def decide_attendance_correction(
    correction_id: str,
    payload: LeaveDecisionIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Setujui (angka diterapkan ke rekap absensi) atau tolak koreksi."""
    return ess_service.decide_attendance_correction(
        db, current_user, correction_id, payload.approved, payload.note
    )


@router.post(
    "/{employee_id}/leave-balance",
    response_model=LeaveBalanceOut,
    status_code=200,
)
def upsert_leave_balance(
    employee_id: str,
    payload: LeaveBalanceUpsertIn,
    db: Session = Depends(get_db),
):
    """Buat/perbarui jatah cuti tahunan karyawan untuk satu periode."""
    return ess_service.upsert_leave_balance(db, employee_id, payload)


@router.get("/{employee_id}/leave-balance", response_model=LeaveBalanceOut | None)
def get_leave_balance(
    employee_id: str,
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    """Jatah cuti karyawan untuk satu periode; null bila belum diatur."""
    return ess_service.get_employee_leave_balance(db, employee_id, year)


@router.get("/contracts/expiring", response_model=list[dict])
def expiring_contracts(within_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return service.expiring_contracts(db, within_days)


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    return service.get_employee(db, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: str, payload: EmployeeUpdate, db: Session = Depends(get_db)):
    return service.update_employee(db, employee_id, payload)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: str, db: Session = Depends(get_db)):
    service.delete_employee(db, employee_id)


# ---------- Kontrak kerja ----------


@router.post("/{employee_id}/contracts", response_model=ContractOut, status_code=201)
def create_contract(employee_id: str, payload: ContractCreate, db: Session = Depends(get_db)):
    return service.create_contract(db, employee_id, payload)


@router.get("/{employee_id}/contracts", response_model=list[ContractOut])
def list_contracts(employee_id: str, db: Session = Depends(get_db)):
    return service.list_contracts(db, employee_id)


@router.patch("/contracts/{contract_id}", response_model=ContractOut)
def update_contract(contract_id: str, payload: ContractUpdate, db: Session = Depends(get_db)):
    return service.update_contract(db, contract_id, payload)


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract_id: str, db: Session = Depends(get_db)):
    service.delete_contract(db, contract_id)


@router.post("/contracts/{contract_id}/sign", response_model=ContractOut)
def sign_contract(contract_id: str, db: Session = Depends(get_db)):
    return service.sign_contract(db, contract_id)


@router.post("/contracts/{contract_id}/file", response_model=ContractOut)
async def upload_contract_file(
    contract_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await service.upload_contract_file(db, contract_id, file)


@router.get("/contracts/{contract_id}/download-url")
def contract_download_url(contract_id: str, db: Session = Depends(get_db)):
    return {"url": service.contract_file_download_url(db, contract_id)}


# ---------- Dokumen HR ----------


@router.post("/{employee_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    employee_id: str,
    file: UploadFile = File(...),
    document_type: HrDocumentType = Form(HrDocumentType.other),
    title: str = Form(""),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await service.upload_document(
        db, employee_id, document_type, title, file, notes, current_user.id
    )


@router.get("/{employee_id}/documents", response_model=list[DocumentOut])
def list_documents(employee_id: str, db: Session = Depends(get_db)):
    return service.list_documents(db, employee_id)


@router.get("/documents/{document_id}/download-url")
def download_url(document_id: str, db: Session = Depends(get_db)):
    return {"url": service.document_download_url(db, document_id)}


# ---------- Asuransi one-to-many — PRD v3.0 Workforce Cloud ----------


@router.get("/{employee_id}/insurances", response_model=list[InsuranceOut])
def list_insurances(employee_id: str, db: Session = Depends(get_db)):
    return service.list_insurances(db, employee_id)


@router.post("/{employee_id}/insurances", response_model=InsuranceOut, status_code=201)
def create_insurance(
    employee_id: str,
    payload: InsuranceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return service.create_insurance(db, employee_id, payload, uploaded_by=current_user.id)


@router.patch("/insurances/{insurance_id}", response_model=InsuranceOut)
def update_insurance(insurance_id: str, payload: InsuranceUpdate, db: Session = Depends(get_db)):
    return service.update_insurance(db, insurance_id, payload)


@router.delete("/insurances/{insurance_id}", status_code=204)
def delete_insurance(insurance_id: str, db: Session = Depends(get_db)):
    service.delete_insurance(db, insurance_id)


@router.post("/insurances/{insurance_id}/card", response_model=InsuranceOut, status_code=201)
async def upload_insurance_card(
    insurance_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    return await service.upload_insurance_file(db, insurance_id, file, kind="card")


@router.post("/insurances/{insurance_id}/policy", response_model=InsuranceOut, status_code=201)
async def upload_insurance_policy(
    insurance_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    return await service.upload_insurance_file(db, insurance_id, file, kind="policy")


@router.get("/insurances/{insurance_id}/card/download-url")
def insurance_card_url(insurance_id: str, db: Session = Depends(get_db)):
    return {"url": service.insurance_file_url(db, insurance_id, kind="card")}


@router.get("/insurances/{insurance_id}/policy/download-url")
def insurance_policy_url(insurance_id: str, db: Session = Depends(get_db)):
    return {"url": service.insurance_file_url(db, insurance_id, kind="policy")}


# ---------- BPJS kartu + valid_until — PRD v3.0 ----------


@router.post("/{employee_id}/bpjs-card", status_code=201)
async def upload_bpjs_card(
    employee_id: str,
    file: UploadFile = File(...),
    bpjs_type: str = Form(...),
    valid_until: str | None = Form(None),
    db: Session = Depends(get_db),
):
    from datetime import date

    vu = None
    if valid_until:
        try:
            vu = date.fromisoformat(valid_until)
        except Exception:
            vu = None
    return await service.upload_bpjs_card(
        db, employee_id, file, bpjs_type=bpjs_type, valid_until=vu
    )


@router.get("/{employee_id}/bpjs-card/{bpjs_type}/download-url")
def bpjs_card_download(employee_id: str, bpjs_type: str, db: Session = Depends(get_db)):
    return {"url": service.bpjs_card_url(db, employee_id, bpjs_type)}
