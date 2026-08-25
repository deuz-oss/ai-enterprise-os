from datetime import datetime

from pydantic import BaseModel


class AppEntitlementOut(BaseModel):
    """Satu aplikasi registry + status lisensi untuk tenant saat ini."""

    key: str
    name: str
    emoji: str
    accent: str
    description: str
    depends_on: list[str]
    licensed: bool
    status: str | None
    expires_at: datetime | None


class TrialActivatedOut(BaseModel):
    app_key: str
    status: str
    expires_at: datetime | None


class LicenseSetIn(BaseModel):
    status: str
    expires_at: datetime | None = None
