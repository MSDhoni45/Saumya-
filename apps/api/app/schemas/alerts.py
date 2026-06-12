import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperatorAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None
    kind: str
    severity: str
    title: str
    body: str
    created_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: uuid.UUID | None
