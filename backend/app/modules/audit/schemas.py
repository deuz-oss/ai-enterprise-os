from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    user_id: UUID | None
    action: str
    entity_type: str | None
    entity_id: UUID | None
    object_key: str | None
    ip: str | None
    created_at: datetime
    detail: Any | None = None


class AuditListOut(BaseModel):
    total: int
    items: list[AuditLogOut]
