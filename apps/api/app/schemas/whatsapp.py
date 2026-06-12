import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Connection management ---------------------------------------------------


class WhatsAppAccountConnectRequest(BaseModel):
    waba_id: str
    phone_number_id: str
    access_token: str = Field(..., description="Permanent or system-user access token from Meta")
    display_name: str | None = None


class WhatsAppAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    display_name: str | None
    phone_number: str
    waba_id: str
    phone_number_id: str
    status: Literal["pending", "connected", "disconnected", "error"]
    connected_at: datetime | None
    created_at: datetime


# --- Outbound send API --------------------------------------------------------


class SendMessageRequest(BaseModel):
    to: str = Field(..., description="Recipient phone number in E.164 format")
    message_type: Literal["text", "image", "document", "template"] = "text"
    text: str | None = Field(None, description="Required when message_type is 'text'")
    media_url: str | None = Field(None, description="Required when message_type is 'image' or 'document'")
    caption: str | None = None
    filename: str | None = Field(None, description="Used for document messages")
    # Template fields — required when `message_type == "template"`. Meta is the
    # source of truth for which templates exist / are approved; we do not keep
    # a local registry.
    template_name: str | None = Field(None, description="Approved Meta template name")
    language_code: str | None = Field(None, description="BCP-47 language code, e.g. 'en_US'")
    template_components: list[dict[str, Any]] | None = Field(
        None, description="Optional header/body/button substitutions per Meta's template spec"
    )


class SendMessageResponse(BaseModel):
    message_id: uuid.UUID
    whatsapp_message_id: str
    status: str


# --- Conversations & messages (read models) -----------------------------------


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: Literal["inbound", "outbound"]
    sender_type: Literal["contact", "ai", "agent", "system"]
    message_type: Literal["text", "image", "document", "audio", "video", "template", "location"]
    content: str | None
    media_url: str | None
    status: Literal["queued", "sent", "delivered", "read", "failed"]
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    failed_at: datetime | None = None
    error_code: str | None = None
    error_title: str | None = None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    whatsapp_account_id: uuid.UUID
    contact_phone: str
    contact_name: str | None
    status: Literal["open", "pending", "handoff", "closed"]
    assigned_user_id: uuid.UUID | None
    last_message_at: datetime | None
    created_at: datetime
    # Populated by the list endpoint via a correlated subquery — not stored on
    # the model column, so defaults to None and is filled in by the route.
    last_message_content: str | None = None
    last_sender_type: str | None = None


class PaginatedConversations(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ConversationUpdateRequest(BaseModel):
    """Partial update for human takeover / hand-back / reassignment.

    Both fields are optional so a caller can change just one (e.g. reassign
    without touching status). Distinguishing "field omitted" from "field set to
    null" matters for `assigned_user_id` (omitted = leave as-is, null = clear
    the assignment/hand back to the AI pool) — the route checks
    `model_fields_set` rather than relying on the default.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "pending", "handoff", "closed"] | None = None
    assigned_user_id: uuid.UUID | None = None


# --- Inbound webhook payload (Meta Cloud API "Messages" webhook shape) --------
# Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components


class WebhookMediaPayload(BaseModel):
    id: str
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None
    filename: str | None = None


class WebhookMessage(BaseModel):
    id: str
    from_: str = Field(..., alias="from")
    timestamp: str
    type: str
    text: dict[str, Any] | None = None
    image: WebhookMediaPayload | None = None
    document: WebhookMediaPayload | None = None
    audio: WebhookMediaPayload | None = None
    video: WebhookMediaPayload | None = None

    model_config = ConfigDict(populate_by_name=True)


class WebhookContactProfile(BaseModel):
    name: str | None = None


class WebhookContact(BaseModel):
    wa_id: str
    profile: WebhookContactProfile | None = None


class WebhookMetadata(BaseModel):
    display_phone_number: str | None = None
    phone_number_id: str


class WebhookStatusError(BaseModel):
    """One entry in a `statuses[].errors` array.

    Meta historically used `code`/`title`; the v17+ payloads add `message` and
    `error_data`. We keep everything optional so we never reject a valid
    delivery just because the shape drifted.
    """

    code: int | None = None
    title: str | None = None
    message: str | None = None
    error_data: dict[str, Any] | None = None
    href: str | None = None

    model_config = ConfigDict(extra="ignore")


class WebhookConversation(BaseModel):
    """Meta's billing/conversation envelope on status callbacks.

    Captured loosely — not used for state-machine decisions today, kept so
    downstream analytics can read pricing/origin without another schema bump.
    """

    id: str | None = None
    expiration_timestamp: str | None = None
    origin: dict[str, Any] | None = None

    model_config = ConfigDict(extra="ignore")


class WebhookPricing(BaseModel):
    billable: bool | None = None
    pricing_model: str | None = None
    category: str | None = None

    model_config = ConfigDict(extra="ignore")


class WebhookStatus(BaseModel):
    """Single status entry in `value.statuses` — one Meta delivery receipt.

    `id` is the `whatsapp_message_id` we stored when the outbound send
    returned 200; that's what we look up against to advance the state.
    `recipient_id` is the contact's wa_id, retained for audit/debug.
    """

    id: str
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: str
    recipient_id: str | None = None
    conversation: WebhookConversation | None = None
    pricing: WebhookPricing | None = None
    errors: list[WebhookStatusError] | None = None

    model_config = ConfigDict(extra="ignore")


class WebhookValue(BaseModel):
    messaging_product: str
    metadata: WebhookMetadata
    contacts: list[WebhookContact] | None = None
    messages: list[WebhookMessage] | None = None
    statuses: list[WebhookStatus] | None = None


class WebhookChange(BaseModel):
    field: str
    value: WebhookValue


class WebhookEntry(BaseModel):
    id: str
    changes: list[WebhookChange]


class WebhookEnvelope(BaseModel):
    object: str
    entry: list[WebhookEntry]
