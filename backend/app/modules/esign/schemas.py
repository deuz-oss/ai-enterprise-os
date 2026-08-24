from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.modules.esign.models import EsignStatus


class EsignSendIn(BaseModel):
    signer_name: str
    signer_email: EmailStr


class EsignRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    provider: str
    provider_document_id: str
    signer_name: str
    signer_email: str
    sign_url: str | None
    status: EsignStatus
    signed_at: datetime | None
    error: str | None
    created_at: datetime


class EsignConfigOut(BaseModel):
    """Info konfigurasi untuk frontend (tanpa rahasia)."""

    provider: str | None
    webhook_ready: bool
