from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    body: str | None
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int
