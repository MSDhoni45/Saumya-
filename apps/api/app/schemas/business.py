import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BusinessUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    industry: str | None = None
    timezone: str | None = None
    onboarding_completed: bool | None = None
    notify_whatsapp_phone: str | None = Field(None, pattern=r"^\+[1-9]\d{6,14}$")


class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: str | None
    timezone: str
    onboarding_completed: bool
    notify_whatsapp_phone: str | None
    created_at: datetime
    updated_at: datetime
