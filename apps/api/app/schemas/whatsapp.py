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
    message_type: Literal["text", "image", "document"] = "text"
    text: str | None = Field(None, description="Required when message_type is 'text'")
    media_url: str | None = Field(None, description="Required when message_type is 'image' or 'document'")
    caption: str | None = None
    filename: str | None = Field(None, description="Used for document messages")


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
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    whatsapp_account_id: uuid.UUID
    contact_phone: str
    contact_name: str | None
    status: Literal["open", "pending", "handoff", "closed"]
    last_message_at: datetime | None
    created_at: datetime


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


class WebhookValue(BaseModel):
    messaging_product: str
    metadata: WebhookMetadata
    contacts: list[WebhookContact] | None = None
    messages: list[WebhookMessage] | None = None
    statuses: list[dict[str, Any]] | None = None


class WebhookChange(BaseModel):
    field: str
    value: WebhookValue


class WebhookEntry(BaseModel):
    id: str
    changes: list[WebhookChange]


class WebhookEnvelope(BaseModel):
    object: str
    entry: list[WebhookEntry]
