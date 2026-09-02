from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.blacklist.models import BlacklistStatus
from pydantic import BaseModel


class BlacklistRequestIn(BaseModel):
    candidate_id: UUID
    reason: str


class BlacklistReviewIn(BaseModel):
    decision: BlacklistStatus
    """Cuma `approved`/`rejected` yang valid di sini -- `pending` ditolak di service."""
    notes: str | None = None


class BlacklistEntryOut(BaseModel):
    id: UUID
    candidate_id: UUID
    candidate_name: str
    reason: str
    status: BlacklistStatus
    requested_by: UUID | None
    requested_by_name: str | None
    requested_at: datetime
    reviewed_by: UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    review_notes: str | None
