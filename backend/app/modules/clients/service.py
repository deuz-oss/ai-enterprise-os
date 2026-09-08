import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.database import assert_not_referenced, parse_uuid
from app.modules import audit
from app.modules.clients.models import (
    Client,
    ClientPortalAccess,
    ClientSite,
    DocumentType,
    LegalDocument,
)
from app.modules.clients.schemas import (
    ClientCreate,
    ClientSiteCreate,
    ClientSiteUpdate,
    ClientUpdate,
)


def _get(db: Session, client_id: str) -> Client:
    client = db.get(Client, parse_uuid(client_id))
    if client is None:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    return client


def create_client(db: Session, payload: ClientCreate) -> Client:
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    audit.log_event(db, action="client.create", entity_type="client", entity_id=client.id)
    return client


def list_clients(db: Session, q: str | None = None) -> list[tuple[Client, int]]:
    """Return `(Client, job_count)` -- job_count dihitung dalam satu query
    (outerjoin+group_by), bukan N+1 per klien."""
    from app.modules.recruitment.models import JobOrder

    stmt = (
        select(Client, func.count(JobOrder.id))
        .outerjoin(JobOrder, JobOrder.client_id == Client.id)
        .group_by(Client.id)
        .order_by(Client.created_at.desc())
    )
    if q:
        stmt = stmt.where(Client.name.ilike(f"%{q}%"))
    return [(cl, count) for cl, count in db.execute(stmt).all()]


def get_client(db: Session, client_id: str) -> Client:
    return _get(db, client_id)


def update_client(db: Session, client_id: str, payload: ClientUpdate) -> Client:
    client = _get(db, client_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    audit.log_event(db, action="client.update", entity_type="client", entity_id=client.id)
    return client


def delete_client(db: Session, client_id: str) -> None:
    client = _get(db, client_id)
    assert_not_referenced(db, "clients", client.id, "Klien")
    client_id_val = client.id
    db.delete(client)
    db.commit()
    audit.log_event(db, action="client.delete", entity_type="client", entity_id=client_id_val)


def _next_version(db: Session, client_id, document_type: DocumentType) -> int:
    current = db.execute(
        select(func.max(LegalDocument.version)).where(
            LegalDocument.client_id == parse_uuid(client_id),
            LegalDocument.document_type == document_type,
        )
    ).scalar()
    return int(current or 0) + 1


async def upload_document(
    db: Session,
    client_id: str,
    document_type: DocumentType,
    title: str,
    file: UploadFile,
    notes: str | None,
    uploaded_by: str | None,
) -> LegalDocument:
    client = _get(db, client_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File kosong")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    file_name = file.filename or "document.pdf"
    object_key = storage.new_object_key(f"clients/{client.id}", file_name)
    content_type = file.content_type or "application/octet-stream"
    storage.put_object(object_key, data, content_type)

    document = LegalDocument(
        client_id=client.id,
        document_type=document_type,
        title=title or file_name,
        version=_next_version(db, str(client.id), document_type),
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
        action="legal_document.upload",
        entity_type="legal_document",
        entity_id=document.id,
        object_key=object_key,
        detail={"client_id": str(client.id), "file_name": file_name, "version": document.version},
    )
    return document


def list_documents(db: Session, client_id: str) -> list[LegalDocument]:
    client = _get(db, client_id)
    return list(client.documents)


def download_url(db: Session, document_id: str) -> str:
    document = db.get(LegalDocument, parse_uuid(document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    audit.log_event(
        db,
        action="legal_document.download_url",
        entity_type="legal_document",
        entity_id=document.id,
        object_key=document.object_key,
        detail={"client_id": str(document.client_id), "file_name": document.file_name},
    )
    return storage.presigned_get_url(document.object_key)


def expiring_contracts(db: Session, within_days: int) -> list[Client]:
    from datetime import date, timedelta

    limit = date.today() + timedelta(days=within_days)
    stmt = (
        select(Client)
        .where(Client.contract_end.is_not(None))
        .where(Client.contract_end <= limit)
        .where(Client.status == "aktif")
        .order_by(Client.contract_end)
    )
    return list(db.execute(stmt).scalars())


def list_client_employees(db: Session, client_id: str):
    """Karyawan eksternal yang PERNAH ditempatkan di klien ini (tab
    Karyawan di ClientDetail) -- lintas periode, beda dari
    `client_portal_attendance` yang scope-nya rekap satu bulan."""
    from app.modules.hrd.models import Employee, EmploymentType
    from app.modules.recruitment.models import JobOrder, Placement

    _get(db, client_id)
    return list(
        db.execute(
            select(Employee)
            .join(Placement, Employee.placement_id == Placement.id)
            .join(JobOrder, Placement.job_order_id == JobOrder.id)
            .where(
                JobOrder.client_id == parse_uuid(client_id),
                Employee.employment_type == EmploymentType.eksternal,
            )
            .order_by(Employee.full_name)
        ).scalars()
    )


# ---------- Portal monitoring klien (link ber-token, tanpa akun) ----------


def _hash_portal_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_portal_access(db: Session, user, client_id: str) -> tuple[ClientPortalAccess, str]:
    """Buat/ganti link portal monitoring klien -- satu baris per klien
    (`uq_client_portal_access_client`), regenerate mencabut yang lama
    (pola sama `payroll.service.submit_to_client`)."""
    client = _get(db, client_id)
    existing = db.execute(
        select(ClientPortalAccess).where(ClientPortalAccess.client_id == client.id)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.flush()
    raw = secrets.token_urlsafe(24)
    access = ClientPortalAccess(
        client_id=client.id,
        token_hash=_hash_portal_token(raw),
        created_by=getattr(user, "id", None),
    )
    db.add(access)
    db.commit()
    db.refresh(access)
    audit.log_event(
        db,
        action="client_portal.access_generated",
        entity_type="client",
        entity_id=client.id,
        detail={"by": getattr(user, "email", "?")},
    )
    return access, raw


def get_portal_access_status(db: Session, client_id: str) -> ClientPortalAccess | None:
    client = _get(db, client_id)
    return db.execute(
        select(ClientPortalAccess).where(ClientPortalAccess.client_id == client.id)
    ).scalar_one_or_none()


def revoke_portal_access(db: Session, client_id: str) -> None:
    client = _get(db, client_id)
    existing = db.execute(
        select(ClientPortalAccess).where(ClientPortalAccess.client_id == client.id)
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Belum ada akses portal untuk klien ini")
    db.delete(existing)
    db.commit()
    audit.log_event(
        db,
        action="client_portal.access_revoked",
        entity_type="client",
        entity_id=client.id,
    )


def _find_portal_access(db: Session, raw_token: str) -> ClientPortalAccess:
    access = db.execute(
        select(ClientPortalAccess).where(
            ClientPortalAccess.token_hash == _hash_portal_token(raw_token)
        )
    ).scalar_one_or_none()
    if access is None:
        raise HTTPException(status_code=404, detail="Link portal tidak valid")
    return access


def client_portal_attendance(
    db: Session, raw_token: str, year: int | None, month: int | None
) -> dict:
    """Ringkasan kehadiran & lembur read-only untuk klien (tanpa akun).

    Endpoint publik TANPA konteks tenant, sehingga seluruh query dibungkus
    `set_tenant(access.tenant_id)` segera setelah token ditemukan (pola
    sama `payroll.service.decide_by_token`)."""
    from datetime import date

    from app.core.tenancy import get_tenant, set_tenant
    from app.modules.hrd.models import Employee, EmploymentType
    from app.modules.payroll.models import AttendanceSummary
    from app.modules.recruitment.models import JobOrder, Placement

    access = _find_portal_access(db, raw_token)
    prev_tenant = get_tenant()
    set_tenant(access.tenant_id)
    try:
        client = db.get(Client, access.client_id)
        if client is None:
            raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
        access.last_accessed_at = datetime.now(UTC)
        db.commit()

        today = date.today()
        y = year or today.year
        m = month or today.month

        rows = db.execute(
            select(AttendanceSummary, Employee)
            .join(Employee, AttendanceSummary.employee_id == Employee.id)
            .join(Placement, Employee.placement_id == Placement.id)
            .join(JobOrder, Placement.job_order_id == JobOrder.id)
            .where(
                JobOrder.client_id == client.id,
                Employee.employment_type == EmploymentType.eksternal,
                AttendanceSummary.year == y,
                AttendanceSummary.month == m,
            )
            .order_by(Employee.full_name)
        ).all()
        return {
            "client_name": client.name,
            "year": y,
            "month": m,
            "rows": [
                {
                    "employee_name": emp.full_name,
                    "employee_no": emp.employee_no,
                    "present_days": summary.present_days,
                    "overtime_hours": summary.overtime_hours,
                    "client_approved": summary.client_approved,
                }
                for summary, emp in rows
            ],
        }
    finally:
        set_tenant(prev_tenant)


# ---------- Lokasi kantor klien (geofencing absensi, Fase 34) ----------


def create_site(db: Session, client_id: str, payload: ClientSiteCreate) -> ClientSite:
    client = _get(db, client_id)
    site = ClientSite(client_id=client.id, **payload.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def list_sites(db: Session, client_id: str) -> list[ClientSite]:
    _get(db, client_id)
    return list(
        db.execute(
            select(ClientSite)
            .where(ClientSite.client_id == parse_uuid(client_id))
            .order_by(ClientSite.name)
        ).scalars()
    )


def list_all_sites(db: Session) -> list[tuple[ClientSite, str]]:
    """Lintas klien -- dropdown pemilihan lokasi di halaman Karyawan."""
    rows = db.execute(
        select(ClientSite, Client.name)
        .join(Client, ClientSite.client_id == Client.id)
        .order_by(Client.name, ClientSite.name)
    ).all()
    return [(site, client_name) for site, client_name in rows]


def _get_site(db: Session, site_id: str) -> ClientSite:
    site = db.get(ClientSite, parse_uuid(site_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan")
    return site


def update_site(db: Session, site_id: str, payload: ClientSiteUpdate) -> ClientSite:
    site = _get_site(db, site_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


def delete_site(db: Session, site_id: str) -> None:
    site = _get_site(db, site_id)
    assert_not_referenced(db, "client_sites", site.id, "Lokasi")
    db.delete(site)
    db.commit()
