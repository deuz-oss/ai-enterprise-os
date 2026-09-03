from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import assert_not_referenced, parse_uuid
from app.modules import audit
from app.modules.hrd.models import (
    ContractSignStatus,
    Employee,
    EmployeeDocument,
    EmployeeStatus,
    EmploymentContract,
    HrDocumentType,
)
from app.modules.hrd.schemas import (
    ContractCreate,
    ContractUpdate,
    EmployeeCreate,
    EmployeeUpdate,
    OnboardCreate,
)
from app.modules.recruitment.models import Placement, PlacementStatus
from app.modules.recruitment.service import update_placement_status


def _get_employee(db: Session, employee_id: str) -> Employee:
    employee = db.get(Employee, parse_uuid(employee_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    return employee


def _generate_employee_no(db: Session) -> str:
    total = db.scalar(select(func.count(Employee.id))) or 0
    return f"EMP-{total + 1:04d}"


def _ensure_unique_employee_no(db: Session, employee_no: str, exclude_id=None) -> None:
    stmt = select(Employee).where(Employee.employee_no == employee_no)
    if exclude_id is not None:
        stmt = stmt.where(Employee.id != exclude_id)
    if db.execute(stmt).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Nomor induk karyawan sudah dipakai")


# ---------- Employees ----------


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    data = payload.model_dump()
    employee_no = (data.pop("employee_no") or "").strip()
    if not employee_no:
        employee_no = _generate_employee_no(db)
    _ensure_unique_employee_no(db, employee_no)
    if data.get("placement_id") is not None:
        placement = db.get(Placement, parse_uuid(str(data["placement_id"])))
        if placement is None:
            raise HTTPException(status_code=404, detail="Placement tidak ditemukan")
        existing = db.execute(
            select(Employee).where(Employee.placement_id == placement.id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Placement ini sudah menjadi data karyawan")
    employee = Employee(employee_no=employee_no, **data)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def list_employees(
    db: Session,
    q: str | None = None,
    status: EmployeeStatus | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[Employee], int]:
    """`limit` default 200, pola sama seperti `recruitment.list_candidates`
    (Batch 1c) -- cegah query tak terbatas begitu jumlah karyawan bertambah."""
    stmt = select(Employee).order_by(Employee.created_at.desc())
    if status is not None:
        stmt = stmt.where(Employee.status == status)
    if q:
        stmt = stmt.where(
            (Employee.full_name.ilike(f"%{q}%")) | (Employee.employee_no.ilike(f"%{q}%"))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


def get_employee(db: Session, employee_id: str) -> Employee:
    return _get_employee(db, employee_id)


def update_employee(db: Session, employee_id: str, payload: EmployeeUpdate) -> Employee:
    employee = _get_employee(db, employee_id)
    data = payload.model_dump(exclude_unset=True)
    new_no = data.pop("employee_no", None)
    if new_no is not None and new_no != employee.employee_no:
        _ensure_unique_employee_no(db, new_no, exclude_id=employee.id)
        employee.employee_no = new_no
    if "user_id" in data:
        data["user_id"] = _resolve_linked_user(db, employee, data["user_id"])
    for field, value in data.items():
        setattr(employee, field, value)
    db.commit()
    db.refresh(employee)
    return employee


def _resolve_linked_user(db: Session, employee: Employee, user_id: UUID | None) -> UUID | None:
    """Validasi tautan akun self-service; None berarti melepas tautan."""
    from app.core.tenancy import get_tenant
    from app.modules.auth.models import User, UserRole

    if user_id is None:
        audit.log_event(
            db,
            action="ess.account_unlinked",
            entity_type="employee",
            entity_id=employee.id,
            detail={"employee_no": employee.employee_no},
        )
        return None
    user = db.get(User, parse_uuid(str(user_id)))
    if user is None or (user.tenant_id and get_tenant() and user.tenant_id != get_tenant()):
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    if user.role != UserRole.employee:
        raise HTTPException(
            status_code=422, detail="Hanya akun dengan role karyawan yang bisa ditautkan"
        )
    if not user.is_active:
        raise HTTPException(status_code=422, detail="Akun tidak aktif")
    taken = db.execute(
        select(Employee).where(Employee.user_id == user.id, Employee.id != employee.id)
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(
            status_code=409,
            detail="Akun sudah tertaut ke karyawan lain",
        )
    audit.log_event(
        db,
        action="ess.account_linked",
        entity_type="employee",
        entity_id=employee.id,
        detail={"user_id": str(user.id), "email": user.email},
    )
    return user.id


def delete_employee(db: Session, employee_id: str) -> None:
    employee = _get_employee(db, employee_id)
    assert_not_referenced(db, "employees", employee.id, "Karyawan")
    db.delete(employee)
    db.commit()


def onboard_from_placement(db: Session, payload: OnboardCreate) -> Employee:
    """Angkat kandidat yang sudah diterima klien menjadi karyawan aktif."""
    placement = db.get(Placement, parse_uuid(str(payload.placement_id)))
    if placement is None:
        raise HTTPException(status_code=404, detail="Placement tidak ditemukan")
    if placement.status == PlacementStatus.cancelled:
        raise HTTPException(status_code=422, detail="Placement yang dibatalkan tidak bisa onboard")
    existing = db.execute(
        select(Employee).where(Employee.placement_id == placement.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Placement ini sudah menjadi data karyawan")

    data = payload.model_dump(exclude={"placement_id", "employee_no"})
    employee_no = (payload.employee_no or "").strip()
    if not employee_no:
        employee_no = _generate_employee_no(db)
    _ensure_unique_employee_no(db, employee_no)

    employee = Employee(
        placement_id=placement.id,
        employee_no=employee_no,
        full_name=placement.candidate.full_name,
        phone=data.get("phone") or placement.candidate.phone,
        join_date=data.get("join_date"),
        status=EmployeeStatus.active,
    )
    db.add(employee)
    db.flush()
    # update_placement_status menandai kandidat placed & mengisi job order.
    update_placement_status(db, str(placement.id), PlacementStatus.onboarded)
    db.refresh(employee)
    return employee


# ---------- Contracts ----------


def _get_contract(db: Session, contract_id: str) -> EmploymentContract:
    contract = db.get(EmploymentContract, parse_uuid(contract_id))
    if contract is None:
        raise HTTPException(status_code=404, detail="Kontrak kerja tidak ditemukan")
    return contract


def _generate_contract_no(db: Session, employee: Employee) -> str:
    """MAX-based (bukan COUNT) + retry di caller -- pola sama seperti
    `recruitment/service.py::_generate_request_id` (temuan audit
    2026-09-02: sebelumnya tidak ada UniqueConstraint sama sekali di
    `contract_no`, tabrakan sukses tersimpan diam-diam)."""
    prefix = f"KON/{employee.employee_no}/"
    existing = db.scalars(
        select(EmploymentContract.contract_no).where(
            EmploymentContract.employee_id == employee.id,
            EmploymentContract.contract_no.like(f"{prefix}%"),
        )
    ).all()
    max_seq = 0
    for no in existing:
        try:
            max_seq = max(max_seq, int(no.rsplit("/", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}{max_seq + 1:02d}"


def create_contract(db: Session, employee_id: str, payload: ContractCreate) -> EmploymentContract:
    employee = _get_employee(db, employee_id)
    data = payload.model_dump()
    if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
        raise HTTPException(status_code=422, detail="Tanggal akhir kontrak sebelum tanggal mulai")
    auto_no = not (data.get("contract_no") or "").strip()

    max_attempts = 5 if auto_no else 1
    for attempt in range(max_attempts):
        if auto_no:
            data["contract_no"] = _generate_contract_no(db, employee)
        contract = EmploymentContract(employee_id=employee.id, **data)
        db.add(contract)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            if attempt == max_attempts - 1:
                raise HTTPException(status_code=409, detail="Nomor kontrak sudah dipakai") from None
    db.refresh(contract)
    return contract


def list_contracts(db: Session, employee_id: str) -> list[EmploymentContract]:
    employee = _get_employee(db, employee_id)
    return list(employee.contracts)


def update_contract(db: Session, contract_id: str, payload: ContractUpdate) -> EmploymentContract:
    contract = _get_contract(db, contract_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)
    if contract.start_date and contract.end_date and contract.end_date < contract.start_date:
        raise HTTPException(status_code=422, detail="Tanggal akhir kontrak sebelum tanggal mulai")
    if contract.sign_status == ContractSignStatus.signed and contract.signed_at is None:
        contract.signed_at = datetime.now(UTC)
    db.commit()
    db.refresh(contract)
    return contract


def delete_contract(db: Session, contract_id: str) -> None:
    contract = _get_contract(db, contract_id)
    db.delete(contract)
    db.commit()


def sign_contract(db: Session, contract_id: str) -> EmploymentContract:
    """Tandai kontrak sudah ditandatangani (TTD fisik tercatat manual)."""
    contract = _get_contract(db, contract_id)
    if contract.sign_status == ContractSignStatus.signed:
        raise HTTPException(status_code=409, detail="Kontrak sudah ditandatangani")
    contract.sign_status = ContractSignStatus.signed
    contract.signed_at = datetime.now(UTC)
    db.commit()
    db.refresh(contract)
    return contract


async def upload_contract_file(
    db: Session, contract_id: str, file: UploadFile
) -> EmploymentContract:
    contract = _get_contract(db, contract_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kontrak kosong")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    file_name = file.filename or "kontrak.pdf"
    content_type = file.content_type or "application/octet-stream"
    object_key = storage.new_object_key(f"contracts/{contract.employee_id}", file_name)
    storage.put_object(object_key, data, content_type)
    contract.object_key = object_key
    contract.file_name = file_name
    contract.mime_type = content_type
    contract.file_size = len(data)
    db.commit()
    db.refresh(contract)
    audit.log_event(
        db,
        action="contract.upload",
        entity_type="employment_contract",
        entity_id=contract.id,
        object_key=object_key,
        detail={"file_name": file_name},
    )
    return contract


def expiring_contracts(db: Session, within_days: int) -> list[dict]:
    """Kontrak karyawan aktif yang berakhir dalam `within_days` ke depan."""
    limit = date.today() + timedelta(days=within_days)
    today = date.today()
    stmt = (
        select(EmploymentContract, Employee)
        .join(Employee, EmploymentContract.employee_id == Employee.id)
        .where(EmploymentContract.end_date.is_not(None))
        .where(EmploymentContract.end_date <= limit)
        .where(Employee.status == EmployeeStatus.active)
        .order_by(EmploymentContract.end_date)
    )
    results: list[dict] = []
    for contract, employee in db.execute(stmt):
        days_left = (contract.end_date - today).days
        results.append(
            {
                "contract_id": contract.id,
                "contract_no": contract.contract_no,
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "employee_no": employee.employee_no,
                "end_date": contract.end_date,
                "days_left": max(days_left, 0),
            }
        )
    return results


# ---------- HR documents ----------


def _next_doc_version(db: Session, employee_id, document_type: HrDocumentType) -> int:
    current = db.execute(
        select(func.max(EmployeeDocument.version)).where(
            EmployeeDocument.employee_id == parse_uuid(str(employee_id)),
            EmployeeDocument.document_type == document_type,
        )
    ).scalar()
    return int(current or 0) + 1


async def upload_document(
    db: Session,
    employee_id: str,
    document_type: HrDocumentType,
    title: str,
    file: UploadFile,
    notes: str | None,
    uploaded_by,
) -> EmployeeDocument:
    employee = _get_employee(db, employee_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    file_name = file.filename or "dokumen.pdf"
    content_type = file.content_type or "application/octet-stream"
    object_key = storage.new_object_key(f"employees/{employee.id}", file_name)
    storage.put_object(object_key, data, content_type)

    document = EmployeeDocument(
        employee_id=employee.id,
        document_type=document_type,
        title=title or file_name,
        version=_next_doc_version(db, employee.id, document_type),
        object_key=object_key,
        file_name=file_name,
        mime_type=content_type,
        file_size=len(data),
        notes=notes,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    audit.log_event(
        db,
        action="employee_document.upload",
        entity_type="employee_document",
        entity_id=document.id,
        object_key=document.object_key,
        detail={
            "employee_id": str(employee.id),
            "title": document.title,
            "version": document.version,
        },
    )
    return document


def list_documents(db: Session, employee_id: str) -> list[EmployeeDocument]:
    employee = _get_employee(db, employee_id)
    return list(employee.documents)


def document_download_url(db: Session, document_id: str) -> str:
    document = db.get(EmployeeDocument, parse_uuid(document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    audit.log_event(
        db,
        action="employee_document.download_url",
        entity_type="employee_document",
        entity_id=document.id,
        object_key=document.object_key,
        detail={"file_name": document.file_name},
    )
    return storage.presigned_get_url(document.object_key)


def contract_file_download_url(db: Session, contract_id: str) -> str:
    contract = _get_contract(db, contract_id)
    if not contract.object_key:
        raise HTTPException(status_code=404, detail="Kontrak belum punya file")
    audit.log_event(
        db,
        action="contract.download_url",
        entity_type="employment_contract",
        entity_id=contract.id,
        object_key=contract.object_key,
        detail={"file_name": contract.file_name},
    )
    return storage.presigned_get_url(contract.object_key)


# ---------- Employee Insurances — PRD v3.0 one-to-many ----------


def _get_insurance(db: Session, insurance_id: str):
    from app.modules.hrd.models import EmployeeInsurance

    ins = db.get(EmployeeInsurance, parse_uuid(insurance_id))
    if not ins:
        raise HTTPException(status_code=404, detail="Asuransi tidak ditemukan")
    return ins


def list_insurances(db: Session, employee_id: str):
    from app.modules.hrd.models import EmployeeInsurance

    _get_employee(db, employee_id)
    stmt = (
        select(EmployeeInsurance)
        .where(EmployeeInsurance.employee_id == parse_uuid(employee_id))
        .order_by(EmployeeInsurance.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


def create_insurance(db: Session, employee_id: str, payload, uploaded_by=None):
    from app.modules.hrd.models import EmployeeInsurance

    _get_employee(db, employee_id)
    data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    ins = EmployeeInsurance(employee_id=parse_uuid(employee_id), uploaded_by=uploaded_by, **data)
    db.add(ins)
    db.commit()
    db.refresh(ins)
    audit.log_event(
        db,
        action="employee.insurance_created",
        entity_type="employee",
        entity_id=parse_uuid(employee_id),
        detail={"policy_no": ins.policy_no},
    )
    return ins


def update_insurance(db: Session, insurance_id: str, payload):
    ins = _get_insurance(db, insurance_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ins, field, value)
    db.commit()
    db.refresh(ins)
    return ins


def delete_insurance(db: Session, insurance_id: str):
    ins = _get_insurance(db, insurance_id)
    db.delete(ins)
    db.commit()


async def upload_insurance_file(
    db: Session, insurance_id: str, file: UploadFile, kind: str = "card"
):
    ins = _get_insurance(db, insurance_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    # PRD v3.0 §5: kartu (JPG/PNG/PDF) ≤5MB, polis (PDF) ≤10MB
    max_bytes = 5 * 1024 * 1024 if kind == "card" else 10 * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Maksimal {max_bytes // (1024 * 1024)} MB")
    file_name = file.filename or f"{kind}.pdf"
    object_key = storage.new_object_key(f"insurances/{ins.id}", file_name)
    storage.put_object(object_key, data, file.content_type or "application/octet-stream")
    if kind == "card":
        ins.card_object_key = object_key
    else:
        ins.policy_object_key = object_key
    db.commit()
    db.refresh(ins)
    audit.log_event(
        db,
        action=f"employee.insurance_{kind}_uploaded",
        entity_type="employee_insurance",
        entity_id=ins.id,
        object_key=object_key,
    )
    return ins


def insurance_file_url(db: Session, insurance_id: str, kind: str = "card") -> str:
    ins = _get_insurance(db, insurance_id)
    key = ins.card_object_key if kind == "card" else ins.policy_object_key
    if not key:
        raise HTTPException(status_code=404, detail="File belum ada")
    audit.log_event(
        db,
        action=f"employee.insurance_{kind}_download",
        entity_type="employee_insurance",
        entity_id=ins.id,
        object_key=key,
    )
    return storage.presigned_get_url(key)


async def upload_bpjs_card(
    db: Session, employee_id: str, file: UploadFile, bpjs_type: str, valid_until=None
):
    emp = _get_employee(db, employee_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maksimal 5 MB")
    file_name = file.filename or f"bpjs_{bpjs_type}.pdf"
    object_key = storage.new_object_key(f"employees/{emp.id}/bpjs", file_name)
    storage.put_object(object_key, data, file.content_type or "application/octet-stream")
    if bpjs_type == "kesehatan":
        emp.bpjs_kesehatan_card_key = object_key
        if valid_until:
            emp.bpjs_kesehatan_valid_until = valid_until
    else:
        emp.bpjs_ketenagakerjaan_card_key = object_key
        if valid_until:
            emp.bpjs_ketenagakerjaan_valid_until = valid_until
    db.commit()
    db.refresh(emp)
    audit.log_event(
        db,
        action="employee.bpjs_card_uploaded",
        entity_type="employee",
        entity_id=emp.id,
        object_key=object_key,
        detail={"type": bpjs_type},
    )
    return emp


def bpjs_card_url(db: Session, employee_id: str, bpjs_type: str) -> str:
    emp = _get_employee(db, employee_id)
    key = (
        emp.bpjs_kesehatan_card_key
        if bpjs_type == "kesehatan"
        else emp.bpjs_ketenagakerjaan_card_key
    )
    if not key:
        raise HTTPException(status_code=404, detail="Kartu BPJS belum ada")
    audit.log_event(
        db,
        action="employee.bpjs_card_download",
        entity_type="employee",
        entity_id=emp.id,
        object_key=key,
    )
    return storage.presigned_get_url(key)
