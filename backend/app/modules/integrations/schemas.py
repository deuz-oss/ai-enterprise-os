from datetime import datetime

from pydantic import BaseModel


class GoogleAuthorizeOut(BaseModel):
    authorize_url: str


class GoogleConnectionStatusOut(BaseModel):
    connected: bool
    google_email: str | None = None
    last_synced_at: datetime | None = None


class GoogleSyncResultOut(BaseModel):
    emails_imported: int
    events_imported: int
    synced_at: datetime
