import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Stage / source enumerations
# ---------------------------------------------------------------------------

LeadStage = Literal["new", "contacted", "qualified", "proposal_sent", "won", "lost"]
LeadSource = Literal["whatsapp", "manual", "import", "referral", "web"]

# ---------------------------------------------------------------------------
# Lead schemas
# ---------------------------------------------------------------------------


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    conversation_id: uuid.UUID | None
    assigned_user_id: uuid.UUID | None
    name: str | None
    phone: str | None
    email: str | None
    budget: str | None
    service_interested: str | None
    stage: str
    source: str
    notes: str | None
    stage_changed_at: datetime
    created_at: datetime
    updated_at: datetime


class PaginatedLeads(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
    pages: int


class LeadUpdateRequest(BaseModel):
    """Partial update — only fields present in the request body are touched.

    `assigned_user_id` follows the same `model_fields_set` contract as
    `ConversationUpdateRequest`: omitted = leave as-is, `null` = clear.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    budget: str | None = None
    service_interested: str | None = None
    stage: LeadStage | None = None
    assigned_user_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Note schemas
# ---------------------------------------------------------------------------


class LeadNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    author_id: uuid.UUID | None
    content: str
    created_at: datetime
    updated_at: datetime


class AddNoteRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10_000)


# ---------------------------------------------------------------------------
# Timeline / event schemas
# ---------------------------------------------------------------------------

LeadEventType = Literal[
    "lead_created",
    "stage_changed",
    "field_updated",
    "note_added",
    "note_deleted",
    "assigned",
]


class LeadEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    actor_id: uuid.UUID | None
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class LeadTimelineResponse(BaseModel):
    events: list[LeadEventResponse]
    notes: list[LeadNoteResponse]
