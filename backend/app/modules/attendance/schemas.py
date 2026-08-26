from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.attendance.models import AttendanceSource, AttendanceStatus


class AttendanceRecordIn(BaseModel):
    employee_id: UUID
    date: date
    status: AttendanceStatus = AttendanceStatus.hadir
    clock_in: datetime | None = None
    clock_out: datetime | None = None
    overtime_hours: int = 0
    notes: str | None = None

    @field_validator("overtime_hours")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Jam lembur tidak boleh negatif")
        return v


class AttendanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    date: date
    status: AttendanceStatus
    clock_in: datetime | None
    clock_out: datetime | None
    clock_in_geo: str | None = None
    clock_out_geo: str | None = None
    has_clock_in_selfie: bool = False
    has_clock_out_selfie: bool = False
    overtime_hours: int
    source: AttendanceSource
    notes: str | None


class ImportRowFailure(BaseModel):
    row: int
    employee_no: str
    error: str


class ImportResultOut(BaseModel):
    inserted: int
    updated: int
    failed: list[ImportRowFailure]
