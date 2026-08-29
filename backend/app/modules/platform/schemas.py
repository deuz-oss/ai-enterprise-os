from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.platform.models import TenantStatus


class TenantCreate(BaseModel):
    name: str
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    admin_email: str
    admin_password: str = Field(min_length=8)
    admin_full_name: str


class TenantUpdate(BaseModel):
    name: str | None = None
    status: TenantStatus | None = None
    billing_mode: str | None = Field(default=None, pattern=r"^(inherit|internal|commercial)$")


class BillingModeUpdate(BaseModel):
    billing_mode: str = Field(pattern=r"^(inherit|internal|commercial)$")


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: TenantStatus
    billing_mode: str = "inherit"
    created_at: datetime


class TenantProvisionedOut(TenantOut):
    """Hasil provisioning: tenant + kredensial login admin pertamanya."""

    admin_email: str
    # Password dikembalikan SEKALI saat provisioning agar bisa diteruskan ke klien.
    admin_initial_password: str
