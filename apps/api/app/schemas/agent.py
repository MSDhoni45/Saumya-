import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Agent configuration -------------------------------------------------------


class QualificationField(BaseModel):
    key: str = Field(..., description="Machine-readable key, e.g. 'budget'")
    label: str = Field(..., description="Human-readable prompt for the LLM, e.g. 'Budget range'")
    required: bool = False


class AiAgentCreateRequest(BaseModel):
    name: str
    agent_type: Literal["sales", "support", "follow_up"] = "sales"
    persona: str | None = Field(None, description="System prompt; falls back to a sensible default")
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = Field(0.4, ge=0, le=2)
    qualification_fields: list[QualificationField] = Field(default_factory=list)
    is_active: bool = True


class AiAgentUpdateRequest(BaseModel):
    name: str | None = None
    persona: str | None = None
    provider: Literal["openai", "anthropic"] | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    qualification_fields: list[QualificationField] | None = None
    is_active: bool | None = None


class AiAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    agent_type: Literal["sales", "support", "follow_up"]
    persona: str
    provider: Literal["openai", "anthropic"]
    model: str
    temperature: float
    qualification_fields: list[dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Sandbox / test endpoint ---------------------------------------------------


class AgentTestMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentTestRequest(BaseModel):
    message: str = Field(..., description="The latest message from the (simulated) contact")
    history: list[AgentTestMessage] = Field(
        default_factory=list, description="Prior turns, oldest first, excluding `message`"
    )
    known_lead_fields: dict[str, str] = Field(
        default_factory=dict, description="Fields already captured for this simulated lead"
    )


class RetrievedChunk(BaseModel):
    document_id: uuid.UUID
    title: str
    content: str
    similarity: float


class AgentTestResponse(BaseModel):
    reply: str
    extracted_lead_fields: dict[str, str]
    retrieved_chunks: list[RetrievedChunk]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int


# --- AI interactions (read model / analytics) ----------------------------------


class AiInteractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    conversation_id: uuid.UUID
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    extracted_lead_fields: dict[str, Any]
    created_at: datetime


# --- Internal shapes: structured LLM output ------------------------------------
# Not exposed over the API — used to parse the model's response into a reply
# plus any newly-volunteered lead-qualification data.


class StructuredAgentReply(BaseModel):
    reply: str = Field(..., description="The message to send back to the contact")
    extracted_lead_fields: dict[str, str] = Field(
        default_factory=dict, description="Any qualification fields newly volunteered in this turn"
    )
    lead_name: str | None = None
    lead_email: str | None = None
    lead_phone: str | None = None
