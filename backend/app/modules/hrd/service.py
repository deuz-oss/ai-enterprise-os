import hashlib
import json
import logging
import secrets
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
    EmployeeMovement,
    EmployeeStatus,
    EmploymentContract,
    EmploymentContractTemplate,
    EmploymentType,
    HrDocumentType,
    OnboardingDocument,
    OnboardingInvite,
    OnboardingInviteStatus,
    VaccineRecord,
    WarningLetter,
    WarningLetterType,
)
from app.modules.hrd.schemas import (
    ContractCreate,
    ContractUpdate,
    EmployeeCreate,
    EmployeeMovementCreate,
    EmployeeUpdate,
    EmploymentContractTemplateCreate,
    EmploymentContractTemplateUpdate,
    OnboardCreate,
    OnboardingSubmitIn,
    VaccineRecordCreate,
)
from app.modules.recruitment.models import Placement, PlacementStatus
from app.modules.recruitment.service import update_placement_status

logger = logging.getLogger(__name__)


def _get_employee(db: Session, employee_id: str) -> Employee:
    employee = db.get(Employee, parse_uuid(employee_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    return employee


def _generate_employee_no(db: Session) -> str:
    total = db.scalar(select(func.count(Employee.id))) or 0
    return f"EMP-{total + 1:04d}"


def _generate_referral_code(db: Session) -> str:
    """Fase 27 -- pola sama `_generate_employee_no` (COUNT-based, tanpa retry
    -- konsisten dgn precedent yang sudah ada, bukan kebutuhan baru)."""
    total = db.scalar(select(func.count(Employee.id)).where(Employee.referral_code.is_not(None)))
    return f"REF-{(total or 0) + 1:05d}"


def _ensure_unique_employee_no(db: Session, employee_no: str, exclude_id=None) -> None:
    stmt = select(Employee).where(Employee.employee_no == employee_no)
    if exclude_id is not None:
        stmt = stmt.where(Employee.id != exclude_id)
    if db.execute(stmt).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Nomor induk karyawan sudah dipakai")


# ---------- Employees ----------


def _pop_employee_json_addresses(data: dict) -> dict:
    """`citizen_address`/`residential_address` itu properti read-only
    (turunan JSON) di model -- simpan ke kolom `*_json` mentahnya, pola
    sama seperti `benefits`/`working_days` milik JobOrder (Fase 26)."""
    if "citizen_address" in data:
        addr = data.pop("citizen_address")
        data["citizen_address_json"] = json.dumps(addr) if addr else None
    if "residential_address" in data:
        addr = data.pop("residential_address")
        data["residential_address_json"] = json.dumps(addr) if addr else None
    return data


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    data = _pop_employee_json_addresses(payload.model_dump())
    employee_no = (data.pop("employee_no") or "").strip()
    if not employee_no:
        employee_no = _generate_employee_no(db)
    _ensure_unique_employee_no(db, employee_no)
    data["referral_code"] = _generate_referral_code(db)
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
    viewer_role: str | None = None,
) -> tuple[list[Employee], int]:
    """`limit` default 200, pola sama seperti `recruitment.list_candidates`
    (Batch 1c) -- cegah query tak terbatas begitu jumlah karyawan bertambah.

    `viewer_role="operations"` membatasi hasil ke karyawan eksternal saja
    -- role ini tidak boleh melihat data karyawan internal (Fase 23)."""
    stmt = select(Employee).order_by(Employee.created_at.desc())
    if status is not None:
        stmt = stmt.where(Employee.status == status)
    if q:
        stmt = stmt.where(
            (Employee.full_name.ilike(f"%{q}%")) | (Employee.employee_no.ilike(f"%{q}%"))
        )
    if viewer_role == "operations":
        stmt = stmt.where(Employee.employment_type == EmploymentType.eksternal)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars())
    return rows, total


def get_employee_by_referral_code(db: Session, code: str) -> Employee | None:
    """Fase 27 -- resolusi kode referral saat kandidat baru masuk lewat
    kode rujukan. Dipanggil lazy dari `recruitment/service.py` (hrd sudah
    impor dari recruitment di file ini, jadi impor sebaliknya harus lazy
    di sisi pemanggil supaya tidak circular)."""
    if not code:
        return None
    return db.execute(select(Employee).where(Employee.referral_code == code)).scalar_one_or_none()


def get_employee(db: Session, employee_id: str, viewer_role: str | None = None) -> Employee:
    employee = _get_employee(db, employee_id)
    if viewer_role == "operations" and employee.employment_type != EmploymentType.eksternal:
        # Jangan bocorkan keberadaan data lewat 404 vs 403 -- 404 supaya Ops
        # tidak bisa membedakan "tidak ada" dari "ada tapi internal" (Fase 23).
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    return employee


def update_employee(db: Session, employee_id: str, payload: EmployeeUpdate) -> Employee:
    employee = _get_employee(db, employee_id)
    data = _pop_employee_json_addresses(payload.model_dump(exclude_unset=True))
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


# ---------- Onboarding self-service (link ber-token, PRD gap #4) ----------


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_onboarding_invite(db: Session, invite_id: str) -> OnboardingInvite:
    invite = db.get(OnboardingInvite, parse_uuid(invite_id))
    if invite is None:
        raise HTTPException(status_code=404, detail="Undangan onboarding tidak ditemukan")
    return invite


def create_onboarding_invite(
    db: Session,
    *,
    user,
    placement_id: str,
    days: int = 14,
    document_types: list[HrDocumentType] | None = None,
) -> tuple[OnboardingInvite, str]:
    """Buat link self-service onboarding untuk kandidat (belum tentu sudah
    jadi Employee -- `apply_onboarding_invite` yang membuatnya kalau perlu).
    Jalur ini independen dari `onboard_from_placement` manual, bukan
    pengganti -- tidak semua kandidat bisa isi form sendiri.

    `document_types` = daftar dokumen yang HR minta dari kandidat kali ini
    (pola MYOHRIS "Setup job assessments for onboard") -- default 3 jenis
    dasar (KTP/NPWP/SKCK) kalau HR tidak memilih sendiri."""
    placement = db.get(Placement, parse_uuid(placement_id))
    if placement is None:
        raise HTTPException(status_code=404, detail="Placement tidak ditemukan")
    if placement.status == PlacementStatus.cancelled:
        raise HTTPException(
            status_code=422, detail="Placement yang dibatalkan tidak bisa dikirimi link onboarding"
        )
    if not 1 <= days <= 90:
        raise HTTPException(status_code=422, detail="Masa berlaku link 1-90 hari")
    if document_types is not None and not document_types:
        raise HTTPException(status_code=422, detail="Pilih minimal satu jenis dokumen")

    # Cabut invite lama yang belum di-apply untuk placement yang sama --
    # pola sama payroll/service.py::submit_to_client mencabut token lama.
    stale = db.execute(
        select(OnboardingInvite).where(
            OnboardingInvite.placement_id == placement.id,
            OnboardingInvite.status != OnboardingInviteStatus.applied,
        )
    ).scalars()
    for s in stale:
        db.delete(s)

    raw = secrets.token_urlsafe(24)
    invite = OnboardingInvite(
        placement_id=placement.id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=days),
        created_by=getattr(user, "id", None),
        requested_document_types_json=json.dumps(
            [t.value for t in document_types] if document_types else ["ktp", "npwp", "skck"]
        ),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    audit.log_event(
        db,
        action="onboarding.invite_created",
        entity_type="onboarding_invite",
        entity_id=invite.id,
        detail={"placement_id": str(placement.id), "by": getattr(user, "email", "?")},
    )
    _send_onboarding_invite_email(placement, raw)
    return invite, raw


def _send_onboarding_invite_email(placement: Placement, raw_token: str) -> None:
    """Kirim link onboarding ke email kandidat, best-effort -- BEDA dari
    `send_quotation_email` yang gagal loudly (422) kalau SMTP belum
    dikonfigurasi. Di sini email cuma SALAH SATU kanal pengiriman link
    (HR tetap dapat linknya dari respons endpoint utk dibagikan manual,
    mis. WhatsApp), bukan aksi utama yang wajib berhasil."""
    from app.core.config import get_settings

    candidate_email = (placement.candidate.email or "").strip() if placement.candidate else ""
    if not candidate_email or not get_settings().email_enabled:
        return
    try:
        from app.modules.notifications.service import send_raw_email

        base = (
            get_settings().cors_origin_list[0].rstrip("/")
            if get_settings().cors_origin_list
            else ""
        )
        link = f"{base}/onboarding/{raw_token}"
        send_raw_email(
            candidate_email,
            "Lengkapi Data Onboarding Anda",
            f"Selamat! Silakan lengkapi data onboarding Anda lewat link berikut:\n{link}",
        )
    except Exception:  # noqa: BLE001 - email tidak boleh gagalkan pembuatan link
        logger.exception("Gagal kirim email undangan onboarding ke %s", candidate_email)


def list_onboarding_invites(
    db: Session, *, placement_id: str | None = None
) -> list[OnboardingInvite]:
    stmt = select(OnboardingInvite).order_by(OnboardingInvite.created_at.desc())
    if placement_id:
        stmt = stmt.where(OnboardingInvite.placement_id == parse_uuid(placement_id))
    return list(db.execute(stmt).scalars())


def get_onboarding_invite_detail(db: Session, invite_id: str) -> dict:
    """Detail undangan untuk direview HR -- termasuk link unduh tiap dokumen
    yang sudah diunggah kandidat."""
    invite = _get_onboarding_invite(db, invite_id)
    documents = list(
        db.execute(
            select(OnboardingDocument).where(OnboardingDocument.invite_id == invite.id)
        ).scalars()
    )
    return {
        "invite": invite,
        "submitted_data": json.loads(invite.submitted_data_json)
        if invite.submitted_data_json
        else {},
        "documents": [
            {
                "id": str(d.id),
                "document_type": d.document_type.value,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "uploaded_at": d.uploaded_at,
                "download_url": storage.presigned_get_url(d.object_key),
            }
            for d in documents
        ],
    }


def apply_onboarding_invite(db: Session, *, user, invite_id: str) -> Employee:
    """Terapkan submission kandidat ke record Employee resmi -- baru boleh
    dipanggil setelah HR review (invite berstatus `submitted`). Employee
    dibuat kalau belum ada (logika sama `onboard_from_placement`), lalu
    field yang disubmit di-pipa lewat `update_employee` yang sudah ada
    (bukan tulis manual satu-satu) supaya jalur update Employee tetap satu
    pintu. Dokumen (`OnboardingDocument`) disalin jadi `EmployeeDocument`
    resmi, reuse `object_key` yang sama tanpa upload ulang."""
    invite = _get_onboarding_invite(db, invite_id)
    if invite.status != OnboardingInviteStatus.submitted:
        raise HTTPException(
            status_code=409, detail="Undangan ini belum disubmit kandidat atau sudah diterapkan"
        )
    placement = db.get(Placement, invite.placement_id)
    if placement is None:
        raise HTTPException(status_code=404, detail="Placement tidak ditemukan")

    employee = db.execute(
        select(Employee).where(Employee.placement_id == placement.id)
    ).scalar_one_or_none()
    if employee is None:
        employee = onboard_from_placement(db, OnboardCreate(placement_id=placement.id))

    submitted = json.loads(invite.submitted_data_json) if invite.submitted_data_json else {}
    submitted.pop("consent", None)
    employee = update_employee(db, str(employee.id), EmployeeUpdate(**submitted))

    documents = list(
        db.execute(
            select(OnboardingDocument).where(OnboardingDocument.invite_id == invite.id)
        ).scalars()
    )
    for doc in documents:
        db.add(
            EmployeeDocument(
                employee_id=employee.id,
                document_type=doc.document_type,
                title=doc.document_type.value,
                object_key=doc.object_key,
                file_name=doc.file_name,
                mime_type=doc.mime_type,
                file_size=doc.file_size,
                uploaded_by=None,
            )
        )

    invite.status = OnboardingInviteStatus.applied
    invite.applied_at = datetime.now(UTC)
    invite.applied_by = getattr(user, "id", None)
    db.commit()
    db.refresh(employee)
    audit.log_event(
        db,
        action="onboarding.applied",
        entity_type="onboarding_invite",
        entity_id=invite.id,
        detail={"employee_id": str(employee.id), "by": getattr(user, "email", "?")},
    )
    return employee


def revoke_onboarding_invite(db: Session, *, user, invite_id: str) -> OnboardingInvite:
    """Matikan link permanen -- buat kasus link salah kirim/kompromi.
    Beda dari `request_onboarding_resubmission` yang tetap membiarkan
    kandidat isi ulang di link yang sama."""
    invite = _get_onboarding_invite(db, invite_id)
    if invite.status == OnboardingInviteStatus.applied:
        raise HTTPException(
            status_code=409, detail="Undangan yang sudah diterapkan tidak bisa dibatalkan"
        )
    invite.status = OnboardingInviteStatus.revoked
    db.commit()
    db.refresh(invite)
    audit.log_event(
        db,
        action="onboarding.revoked",
        entity_type="onboarding_invite",
        entity_id=invite.id,
        detail={"by": getattr(user, "email", "?")},
    )
    return invite


def request_onboarding_resubmission(db: Session, *, user, invite_id: str) -> OnboardingInvite:
    """Tolak submission kandidat & minta isi ulang -- token TETAP berfungsi
    dan `submitted_data_json` TIDAK dihapus (jadi referensi/prefill saat
    kandidat balik ke link yang sama). Placement DIKEMBALIKAN ke `hired`
    (kebalikan dari auto-advance di `submit_onboarding_data`) -- kartu
    Kanban tidak boleh terus menampilkan "onboarded" selagi HR masih minta
    kandidat memperbaiki data."""
    invite = _get_onboarding_invite(db, invite_id)
    if invite.status != OnboardingInviteStatus.submitted:
        raise HTTPException(status_code=409, detail="Undangan ini belum disubmit kandidat")
    invite.status = OnboardingInviteStatus.invited
    db.commit()
    db.refresh(invite)
    update_placement_status(db, str(invite.placement_id), PlacementStatus.hired)
    audit.log_event(
        db,
        action="onboarding.resubmission_requested",
        entity_type="onboarding_invite",
        entity_id=invite.id,
        detail={"by": getattr(user, "email", "?")},
    )
    return invite


# ---------- Onboarding self-service -- publik (tanpa akun, via token) ----------
# Guard lisensi/tenant TIDAK berlaku di sini -- akses dikontrol token +
# kedaluwarsa, pola sama `payroll/service.py::decide_by_token`.

ONBOARDING_DOC_ALLOWED_MIME = ("application/pdf", "image/png", "image/jpeg")
ONBOARDING_DOC_MAX_BYTES = 10 * 1024 * 1024


def _find_invite_by_token(db: Session, raw_token: str) -> OnboardingInvite:
    invite = db.execute(
        select(OnboardingInvite).where(OnboardingInvite.token_hash == _hash_token(raw_token))
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Link onboarding tidak valid")
    if invite.status == OnboardingInviteStatus.revoked:
        raise HTTPException(status_code=409, detail="Link onboarding ini sudah dibatalkan")
    if invite.status == OnboardingInviteStatus.applied:
        raise HTTPException(status_code=409, detail="Data onboarding ini sudah diterapkan")
    expires = invite.expires_at
    now = datetime.now(UTC)
    if expires.tzinfo is None:
        now = now.replace(tzinfo=None)
    if expires < now:
        raise HTTPException(status_code=410, detail="Link onboarding sudah kedaluwarsa")
    return invite


def onboarding_invite_public_view(db: Session, raw_token: str) -> dict:
    """Ringkasan untuk kandidat: nama (prefill), status, data yang pernah
    disubmit (buat resume kalau balik lagi), dan dokumen yang sudah ada."""
    from app.core.tenancy import get_tenant, set_tenant

    invite = _find_invite_by_token(db, raw_token)
    prev_tenant = get_tenant()
    set_tenant(invite.tenant_id)
    try:
        placement = db.get(Placement, invite.placement_id)
        documents = list(
            db.execute(
                select(OnboardingDocument).where(OnboardingDocument.invite_id == invite.id)
            ).scalars()
        )
        return {
            "candidate_name": placement.candidate.full_name if placement else None,
            "status": invite.status.value,
            "expires_at": invite.expires_at,
            "requested_document_types": invite.requested_document_types,
            "submitted_data": (
                json.loads(invite.submitted_data_json) if invite.submitted_data_json else {}
            ),
            "documents": [
                {"document_type": d.document_type.value, "file_name": d.file_name}
                for d in documents
            ],
        }
    finally:
        set_tenant(prev_tenant)


def submit_onboarding_data(db: Session, raw_token: str, payload: OnboardingSubmitIn) -> dict:
    """Kandidat menyelesaikan pengisian form -- placement langsung dipindah
    ke stage `onboarded` di sini (bukan menunggu HR klik "Terapkan"), pola
    MYOHRIS: kartu Kanban pindah begitu kandidat selesai isi data, review &
    `apply_onboarding_invite` (yang menulis Employee resmi) tetap terpisah
    setelahnya. Simetris dengan `request_onboarding_resubmission` yang
    mengembalikan placement ke `hired` kalau HR minta isi ulang."""
    from app.core.tenancy import get_tenant, set_tenant

    invite = _find_invite_by_token(db, raw_token)
    if not payload.consent:
        raise HTTPException(
            status_code=422, detail="Persetujuan pemrosesan data pribadi (UU PDP) wajib dicentang"
        )
    prev_tenant = get_tenant()
    set_tenant(invite.tenant_id)
    try:
        data = payload.model_dump(exclude={"consent"})
        invite.submitted_data_json = json.dumps(data, default=str)
        invite.consent = True
        invite.status = OnboardingInviteStatus.submitted
        invite.submitted_at = datetime.now(UTC)
        db.commit()
        update_placement_status(db, str(invite.placement_id), PlacementStatus.onboarded)
    finally:
        set_tenant(prev_tenant)
    return {"status": invite.status.value, "submitted_at": invite.submitted_at}


async def upload_onboarding_document(
    db: Session, raw_token: str, document_type: HrDocumentType, file: UploadFile
) -> dict:
    from app.core.tenancy import get_tenant, set_tenant

    invite = _find_invite_by_token(db, raw_token)
    if document_type.value not in invite.requested_document_types:
        raise HTTPException(
            status_code=422, detail="Jenis dokumen ini tidak diminta untuk undangan ini"
        )
    mime = file.content_type or ""
    if mime not in ONBOARDING_DOC_ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="Format dokumen harus PDF, PNG, atau JPEG")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    if len(data) > ONBOARDING_DOC_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Ukuran dokumen maksimal 10 MB")

    prev_tenant = get_tenant()
    set_tenant(invite.tenant_id)
    try:
        # Ganti (bukan versioning) -- unggah ulang jenis yang sama menimpa yang lama.
        existing = list(
            db.execute(
                select(OnboardingDocument).where(
                    OnboardingDocument.invite_id == invite.id,
                    OnboardingDocument.document_type == document_type,
                )
            ).scalars()
        )
        for old in existing:
            db.delete(old)
        file_name = file.filename or f"{document_type.value}.pdf"
        object_key = storage.new_object_key(f"onboarding/{invite.id}", file_name)
        storage.put_object(object_key, data, mime)
        document = OnboardingDocument(
            invite_id=invite.id,
            document_type=document_type,
            object_key=object_key,
            file_name=file_name,
            mime_type=mime,
            file_size=len(data),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
    finally:
        set_tenant(prev_tenant)
    return {"document_type": document.document_type.value, "file_name": document.file_name}


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


def send_contract_for_signature(
    db: Session, *, contract_id: str, signer_name: str, signer_email: str
):
    """Kirim kontrak kerja ke penyedia TTE + email asli ke calon karyawan.

    Gap 2026-09-07 (temuan sama seperti surat penawaran lewat perbandingan
    alur MYOHRIS): `esign.service.send_contract` sebelumnya cuma upload ke
    provider (Privy) atau simulasi lokal (sandbox) -- TIDAK ADA email dari
    kita sendiri yang meminta karyawan meninjau & menandatangani. Sekarang
    email dikirim eksplisit lewat SMTP kita sendiri, pola sama "fail
    loudly" dengan `recruitment.service.send_offering_letter`. Fungsi ini
    (bukan `esign.service.send_contract` langsung) yang jadi target
    `POST /esign/contracts/{id}/send` -- `esign.service` sengaja tetap
    generik/tidak tahu soal Employee/email (dipakai juga oleh agreement
    klien & surat penawaran)."""
    from app.core.config import get_settings as get_app_settings
    from app.modules.esign.service import send_contract as esign_send_contract
    from app.modules.notifications.service import send_raw_email_with_attachment
    from app.modules.platform.models import Tenant
    from app.modules.recruitment.service import get_hr_document_settings

    contract = _get_contract(db, contract_id)
    if not contract.object_key:
        raise HTTPException(
            status_code=422, detail="Kontrak belum memiliki file untuk ditandatangani"
        )
    if not get_app_settings().email_enabled:
        raise HTTPException(
            status_code=422,
            detail=(
                "SMTP belum dikonfigurasi -- hubungi admin platform untuk "
                "mengaktifkan pengiriman email"
            ),
        )
    employee = _get_employee(db, str(contract.employee_id))
    file_bytes = storage.get_object(contract.object_key)

    request = esign_send_contract(db, contract.id, signer_name, signer_email)

    tenant = db.get(Tenant, contract.tenant_id)
    tenant_name = tenant.name if tenant else "perusahaan kami"
    return_emails = get_hr_document_settings(db).return_emails
    sign_note = (
        f"\n\nAnda juga bisa menandatangani secara elektronik lewat tautan berikut: "
        f"{request.sign_url}"
        if request.sign_url
        else ""
    )
    maintype, _, subtype = (contract.mime_type or "application/octet-stream").partition("/")
    send_raw_email_with_attachment(
        signer_email,
        f"Kontrak Kerja - {employee.full_name} - {tenant_name}",
        (
            f"Selamat bergabung dengan {tenant_name}, {employee.full_name}.\n\n"
            "Bersama email ini kami sampaikan dokumen kontrak kerja yang memuat syarat "
            "dan ketentuan terkait posisi Anda.\n\n"
            "Mohon untuk dapat meninjau dokumen tersebut dengan saksama. Apabila Anda "
            "telah menyetujui isi dokumen tersebut, silakan melakukan proses "
            "penandatanganan. Selanjutnya, mohon untuk mengirimkan kembali dokumen yang "
            f"telah ditandatangani tersebut melalui email ke {return_emails}.{sign_note}\n\n"
            "Apabila terdapat pertanyaan atau hal yang memerlukan klarifikasi lebih "
            "lanjut, jangan ragu untuk menghubungi tim HR kami.\n\n"
            f"Kami menantikan kehadiran Anda untuk menjadi bagian dari {tenant_name}."
        ),
        attachment_bytes=file_bytes,
        attachment_filename=contract.file_name or f"{contract.contract_no}.pdf",
        attachment_maintype=maintype or "application",
        attachment_subtype=subtype or "octet-stream",
    )
    return request


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


# ---------- Template & generate dokumen kontrak karyawan (Fase 25) ----------


def _get_contract_template(db: Session, template_id: str) -> EmploymentContractTemplate:
    tmpl = db.get(EmploymentContractTemplate, parse_uuid(template_id))
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template kontrak tidak ditemukan")
    return tmpl


def create_contract_template(
    db: Session, payload: EmploymentContractTemplateCreate
) -> EmploymentContractTemplate:
    data = payload.model_dump()
    data["field_schema"] = json.dumps(data["field_schema"])
    tmpl = EmploymentContractTemplate(**data)
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def list_contract_templates(db: Session) -> list[EmploymentContractTemplate]:
    stmt = select(EmploymentContractTemplate).order_by(EmploymentContractTemplate.name)
    return list(db.scalars(stmt))


def update_contract_template(
    db: Session, template_id: str, payload: EmploymentContractTemplateUpdate
) -> EmploymentContractTemplate:
    tmpl = _get_contract_template(db, template_id)
    data = payload.model_dump(exclude_unset=True)
    if "field_schema" in data:
        data["field_schema"] = json.dumps(data["field_schema"])
    for field, value in data.items():
        setattr(tmpl, field, value)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def _format_contract_list_value(values: list, list_style: str) -> list[str]:
    """Beri prefix nomor/abjad manual per item -- rendering.py sengaja
    tidak tahu soal gaya penomoran (lihat komentar di
    `presales/rendering.py::render_document_docx`)."""
    items = [str(v) for v in values]
    if list_style == "alpha":
        labels = [chr(ord("a") + i) for i in range(len(items))]
    else:
        labels = [str(i + 1) for i in range(len(items))]
    return [f"{label}. {item}" for label, item in zip(labels, items, strict=True)]


def generate_contract_document(
    db: Session, contract_id: str, template_id: str, field_values: dict
) -> EmploymentContract:
    """Generate dokumen `.docx` dari template, isi `object_key` kontrak --
    langkah download/edit-manual/upload-ulang/kirim-esign setelahnya REUSE
    endpoint yang sudah ada (`upload_contract_file`, `contract_file_
    download_url`, `POST /esign/contracts/{id}/send`), tidak ada endpoint
    baru untuk 3 langkah itu (lihat plan Fase 25)."""
    from app.modules.presales.rendering import render_document_docx, store_generated_document

    contract = _get_contract(db, contract_id)
    template = _get_contract_template(db, template_id)
    schema = json.loads(template.field_schema)

    sections: list[tuple[str, str | list[str]]] = []
    for f in schema:
        raw = field_values.get(f["key"])
        if f.get("type") == "list":
            values = raw if isinstance(raw, list) else []
            list_style = f.get("list_style", "numeric")
            sections.append((f["label"], _format_contract_list_value(values, list_style)))
        else:
            sections.append((f["label"], str(raw) if raw is not None else "-"))

    employee = _get_employee(db, str(contract.employee_id))
    docx_bytes = render_document_docx(
        title="Perjanjian Kerja",
        subtitle=employee.full_name,
        sections=sections,
        footer_text=template.footer_text,
    )
    file_name = f"kontrak-{contract.id}.docx"
    object_key = store_generated_document(
        object_prefix="contracts",
        file_name=file_name,
        data=docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    contract.template_id = template.id
    contract.field_values = json.dumps(field_values)
    contract.object_key = object_key
    contract.file_name = file_name
    contract.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    contract.file_size = len(docx_bytes)
    db.commit()
    db.refresh(contract)
    audit.log_event(
        db,
        action="contract.generated_document",
        entity_type="employment_contract",
        entity_id=contract.id,
        object_key=object_key,
        detail={"template_id": str(template.id)},
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


# ---------- Warning letters (Fase 23 butir 3) ----------


async def create_warning_letter(
    db: Session,
    employee_id: str,
    letter_type: WarningLetterType,
    reason: str,
    issued_at: date | None,
    file: UploadFile | None,
    issued_by,
) -> WarningLetter:
    employee = _get_employee(db, employee_id)
    issued = issued_at or date.today()
    object_key = None
    file_name = None
    mime_type = None
    file_size = 0
    if file is not None:
        data = await file.read()
        if data:
            if len(data) > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
            file_name = file.filename or "surat-peringatan.pdf"
            mime_type = file.content_type or "application/octet-stream"
            object_key = storage.new_object_key(
                f"employees/{employee.id}/warning-letters", file_name
            )
            storage.put_object(object_key, data, mime_type)
            file_size = len(data)

    letter = WarningLetter(
        employee_id=employee.id,
        letter_type=letter_type,
        reason=reason,
        issued_at=issued,
        valid_until=issued + timedelta(days=180),
        object_key=object_key,
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        issued_by=issued_by,
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    audit.log_event(
        db,
        action="warning_letter.create",
        entity_type="warning_letter",
        entity_id=letter.id,
        object_key=letter.object_key,
        detail={"employee_id": str(employee.id), "letter_type": letter_type.value},
    )
    return letter


def list_warning_letters(db: Session, employee_id: str) -> list[WarningLetter]:
    employee = _get_employee(db, employee_id)
    return list(employee.warning_letters)


def warning_letter_download_url(db: Session, letter_id: str) -> str:
    letter = db.get(WarningLetter, parse_uuid(letter_id))
    if letter is None or not letter.object_key:
        raise HTTPException(status_code=404, detail="Surat peringatan tidak ditemukan")
    return storage.presigned_get_url(letter.object_key)


# ---------- Movements & vaccine records (Fase 26) ----------


def create_employee_movement(
    db: Session, employee_id: str, payload: EmployeeMovementCreate, created_by
) -> EmployeeMovement:
    employee = _get_employee(db, employee_id)
    movement = EmployeeMovement(
        employee_id=employee.id, created_by=created_by, **payload.model_dump()
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


def list_employee_movements(db: Session, employee_id: str) -> list[EmployeeMovement]:
    employee = _get_employee(db, employee_id)
    return list(employee.movements)


def create_vaccine_record(
    db: Session, employee_id: str, payload: VaccineRecordCreate
) -> VaccineRecord:
    employee = _get_employee(db, employee_id)
    record = VaccineRecord(employee_id=employee.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_vaccine_records(db: Session, employee_id: str) -> list[VaccineRecord]:
    employee = _get_employee(db, employee_id)
    return list(employee.vaccine_records)


def set_employee_payroll_lock(db: Session, employee_id: str, locked: bool) -> Employee:
    """Kunci/buka payroll level karyawan -- Fase 26 butir 4. Enforcement
    pemblokiran edit slip ada di `payroll/service.py`, bukan di sini."""
    employee = _get_employee(db, employee_id)
    employee.payroll_locked = locked
    employee.payroll_locked_at = datetime.now(UTC) if locked else None
    db.commit()
    db.refresh(employee)
    audit.log_event(
        db,
        action="employee.payroll_lock_set" if locked else "employee.payroll_lock_cleared",
        entity_type="employee",
        entity_id=employee.id,
    )
    return employee


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
