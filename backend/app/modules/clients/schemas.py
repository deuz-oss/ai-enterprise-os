from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.clients.models import ClientStatus, DocumentType


class ClientCreate(BaseModel):
    name: str
    npwp: str | None = None
    address: str | None = None
    pic_name: str | None = None
    pic_phone: str | None = None
    pic_email: str | None = None
    contract_start: date | None = None
    contract_end: date | None = None
    lead_id: UUID | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    npwp: str | None = None
    address: str | None = None
    pic_name: str | None = None
    pic_phone: str | None = None
    pic_email: str | None = None
    status: ClientStatus | None = None
    contract_start: date | None = None
    contract_end: date | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    npwp: str | None
    address: str | None
    pic_name: str | None
    pic_phone: str | None
    pic_email: str | None
    status: ClientStatus
    contract_start: date | None
    contract_end: date | None
    lead_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    document_type: DocumentType
    title: str
    version: int
    file_name: str
    mime_type: str
    file_size: int
    notes: str | None
    uploaded_at: datetime


class ClientPortalAccessOut(BaseModel):
    """Status akses portal klien -- TIDAK PERNAH menyertakan token mentah
    (itu cuma muncul sekali di response `generate_portal_access`)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    last_accessed_at: datetime | None


class ClientSiteCreate(BaseModel):
    name: str
    address: str | None = None
    latitude: Decimal
    longitude: Decimal
    radius_meters: int


class ClientSiteUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    radius_meters: int | None = None


class ClientSiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    name: str
    address: str | None
    latitude: Decimal
    longitude: Decimal
    radius_meters: int
    created_at: datetime


class ClientSiteWithClientOut(ClientSiteOut):
    """Dipakai `GET /clients/sites` (lintas klien) -- dropdown Karyawan
    perlu tahu lokasi itu milik klien mana."""

    client_name: str
