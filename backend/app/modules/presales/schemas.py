from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.presales.models import ActivityType, LeadStage


class LeadCreate(BaseModel):
    company_name: str
    industry: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    estimated_headcount: int | None = None
    estimated_value: float | None = None
    stage: LeadStage = LeadStage.lead
    notes: str | None = None


class LeadUpdate(BaseModel):
    company_name: str | None = None
    industry: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    estimated_headcount: int | None = None
    estimated_value: float | None = None
    stage: LeadStage | None = None
    notes: str | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    industry: str | None
    contact_name: str | None
    contact_phone: str | None
    contact_email: str | None
    estimated_headcount: int | None
    estimated_value: float | None
    stage: LeadStage
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ActivityCreate(BaseModel):
    activity_type: ActivityType = ActivityType.note
    content: str


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: ActivityType
    content: str
    created_at: datetime


class FunnelStage(BaseModel):
    stage: LeadStage
    count: int
    total_estimated_value: float


class FunnelStats(BaseModel):
    stages: list[FunnelStage]
    total_leads: int
    won_leads: int
    lost_leads: int
