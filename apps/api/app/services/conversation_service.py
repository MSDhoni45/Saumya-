import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.schemas.whatsapp import WebhookContact, WebhookMediaPayload, WebhookMessage
from app.services.whatsapp_client import WhatsAppClient

# Inbound message types we persist a `media_url` for once the binary has been
# fetched and re-hosted in our own storage (never store Meta's short-lived CDN
# URLs — they expire within minutes).
_MEDIA_MESSAGE_TYPES = {"image", "document", "audio", "video"}


async def get_or_create_conversation(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    whatsapp_account_id: uuid.UUID,
    contact: WebhookContact,
) -> Conversation:
    """Find the conversation for this contact on this number, or create one.

    Uses an upsert on the `(whatsapp_account_id, contact_phone)` unique index so
    concurrent webhook deliveries for a brand-new contact can't race into two rows.
    """
    contact_name = contact.profile.name if contact.profile else None

    stmt = (
        pg_insert(Conversation)
        .values(
            business_id=business_id,
            whatsapp_account_id=whatsapp_account_id,
            contact_phone=contact.wa_id,
            contact_name=contact_name,
        )
        .on_conflict_do_update(
            index_elements=[Conversation.whatsapp_account_id, Conversation.contact_phone],
            set_={"contact_name": contact_name} if contact_name else {},
        )
        .returning(Conversation)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


def _extract_text_and_media(message: WebhookMessage) -> tuple[str | None, WebhookMediaPayload | None]:
    if message.type == "text" and message.text:
        return message.text.get("body"), None
    media = message.image or message.document or message.audio or message.video
    caption = media.caption if media else None
    return caption, media


async def store_inbound_message(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    conversation: Conversation,
    whatsapp_message: WebhookMessage,
    media_url: str | None = None,
) -> Message | None:
    """Persist an inbound message, idempotently keyed by `whatsapp_message_id`.

    Returns ``None`` (and persists nothing) if this `whatsapp_message_id` was
    already stored — Meta redelivers webhook events on timeout/retry, so the
    unique index is the source of truth, not an in-memory check.
    """
    content, media = _extract_text_and_media(whatsapp_message)
    if media and not media_url:
        # Caller couldn't fetch/re-host the media — record the message anyway so
        # the thread isn't missing an entry, just without a resolvable URL yet.
        media_url = None

    stmt = (
        pg_insert(Message)
        .values(
            conversation_id=conversation.id,
            business_id=business_id,
            direction="inbound",
            sender_type="contact",
            message_type=whatsapp_message.type,
            content=content,
            media_url=media_url,
            whatsapp_message_id=whatsapp_message.id,
            status="delivered",
            created_at=datetime.fromtimestamp(int(whatsapp_message.timestamp), tz=timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=[Message.whatsapp_message_id])
        .returning(Message)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def store_outbound_message(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    sender_type: str,
    message_type: str,
    content: str | None,
    media_url: str | None,
    whatsapp_message_id: str,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        business_id=business_id,
        direction="outbound",
        sender_type=sender_type,
        message_type=message_type,
        content=content,
        media_url=media_url,
        whatsapp_message_id=whatsapp_message_id,
        status="sent",
    )
    session.add(message)
    await session.flush()
    return message


async def fetch_and_store_inbound_media(
    session: AsyncSession,
    *,
    client: WhatsAppClient,
    media: WebhookMediaPayload,
    storage_uploader,
) -> str | None:
    """Resolve a Meta `media_id` to bytes and re-host it via the provided uploader.

    `storage_uploader` is an injected async callable `(bytes, mime_type, filename) -> str`
    (e.g. uploading to Supabase Storage) — kept generic here so this service has
    no direct dependency on a specific storage backend.
    """
    media_meta = await client.get_media_url(media.id)
    media_bytes = await client.download_media(media_meta["url"])
    return await storage_uploader(media_bytes, media_meta.get("mime_type", media.mime_type), media.filename)


async def get_account_by_phone_number_id(session: AsyncSession, phone_number_id: str) -> WhatsAppAccount | None:
    stmt = select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == phone_number_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
