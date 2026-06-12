import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.schemas.whatsapp import WebhookContact, WebhookMediaPayload, WebhookMessage, WebhookStatus
from app.services import operator_alert_service
from app.services.whatsapp_client import WhatsAppClient

logger = logging.getLogger(__name__)

# Monotonic rank for the Meta delivery state machine. We only advance forward —
# Meta routinely redelivers and reorders callbacks (a `read` can arrive before
# its matching `delivered` under load), and naive "last write wins" would cause
# the UI to flap between states. `failed` is terminal: once a send has been
# reported failed, no later `delivered`/`read` should resurrect it.
_STATUS_RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 4}

# Map a target status to the timestamp column it owns. `failed` writes both
# `failed_at` and the error metadata; `sent` has no dedicated column (the row's
# `created_at` already records when we accepted it).
_STATUS_TIMESTAMP_COLUMN = {
    "delivered": "delivered_at",
    "read": "read_at",
    "failed": "failed_at",
}

# Inbound message types we persist a `media_url` for once the binary has been
# fetched and re-hosted in our own storage (never store Meta's short-lived CDN
# URLs — they expire within minutes).
_MEDIA_MESSAGE_TYPES = {"image", "document", "audio", "video"}

# WhatsApp Cloud API only permits free-form (non-template) outbound messages
# within 24 hours of the contact's last inbound message. Outside this window,
# only pre-approved template messages may be sent — Meta returns error 131047
# ("Re-engagement message") for free-form sends past the window. Template sends
# are always permitted.
SERVICE_WINDOW = timedelta(hours=24)


async def get_last_inbound_at(
    session: AsyncSession, conversation_id: uuid.UUID
) -> datetime | None:
    """Most recent inbound message timestamp for a conversation, or ``None`` if
    the contact has never messaged in (proactive-only thread)."""
    stmt = select(func.max(Message.created_at)).where(
        Message.conversation_id == conversation_id,
        Message.direction == "inbound",
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def is_within_service_window(
    last_inbound_at: datetime | None, *, now: datetime | None = None
) -> bool:
    """True iff a free-form message may be sent right now.

    ``None`` last-inbound means the contact has never messaged the business —
    the window has never opened, so only template sends are permitted.
    """
    if last_inbound_at is None:
        return False
    reference = now or datetime.now(tz=timezone.utc)
    return reference - last_inbound_at <= SERVICE_WINDOW


async def store_system_message(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
) -> Message:
    """Write a system-authored note into a conversation thread.

    Used for operator-visible events that have no Meta wamid (e.g. an AI reply
    suppressed because the 24-hour window has closed). Direction is ``outbound``
    so it sorts alongside agent/AI replies in the inbox, but ``sender_type`` is
    ``system`` so the UI can render it differently.
    """
    message = Message(
        conversation_id=conversation_id,
        business_id=business_id,
        direction="outbound",
        sender_type="system",
        message_type="text",
        content=content,
        media_url=None,
        whatsapp_message_id=None,
        status="sent",
    )
    session.add(message)
    await session.flush()
    return message


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


async def apply_message_status(
    session: AsyncSession,
    *,
    status_event: WebhookStatus,
) -> Message | None:
    """Advance an outbound message's status from a Meta delivery callback.

    Returns the updated row if a forward transition occurred, ``None`` otherwise
    (unknown message id, duplicate callback, or out-of-order arrival that would
    move the state backwards).

    Caller is responsible for ``session.commit()`` — kept transactional so a
    batch of callbacks in one webhook delivery either all land or none do.
    """
    stmt = select(Message).where(Message.whatsapp_message_id == status_event.id)
    message = (await session.execute(stmt)).scalar_one_or_none()

    if message is None:
        # Race against an outbound send still being committed in another tx,
        # or a callback for a wamid we never stored (a different env's traffic
        # leaking in). Don't 500 — Meta will retry until our row exists, or
        # forever for genuinely foreign ids.
        logger.info("Status callback for unknown whatsapp_message_id=%s — ignoring", status_event.id)
        return None

    new_rank = _STATUS_RANK[status_event.status]
    current_rank = _STATUS_RANK.get(message.status, 0)

    # `failed` is terminal and can never be reverted; everything else only
    # advances forward. `<=` rather than `<` so duplicate redeliveries (same
    # rank, same wamid) are a clean no-op without an UPDATE round trip.
    if message.status == "failed" or new_rank <= current_rank:
        return None

    try:
        event_ts = datetime.fromtimestamp(int(status_event.timestamp), tz=timezone.utc)
    except (TypeError, ValueError):
        # Meta has historically sent non-integer timestamps on some edge events
        # — fall back to "now" so we still record the transition rather than
        # dropping the callback.
        event_ts = datetime.now(tz=timezone.utc)

    message.status = status_event.status
    timestamp_column = _STATUS_TIMESTAMP_COLUMN.get(status_event.status)
    if timestamp_column is not None:
        setattr(message, timestamp_column, event_ts)

    if status_event.status == "failed" and status_event.errors:
        first = status_event.errors[0]
        message.error_code = str(first.code) if first.code is not None else None
        message.error_title = first.title or first.message

    # Terminal failure → surface to the operator alert inbox so a human can
    # re-engage the contact (the AI loop will not retry a failed wamid).
    if status_event.status == "failed":
        error_code = getattr(message, "error_code", None) or "unknown"
        error_title = getattr(message, "error_title", None) or "delivery failed"
        await operator_alert_service.create_alert(
            session,
            business_id=message.business_id,
            conversation_id=message.conversation_id,
            message_id=message.id,
            kind=operator_alert_service.ALERT_KIND_STATUS_FAILED,
            title="Outbound message failed",
            body=f"WhatsApp reported delivery failure (code={error_code}): {error_title}",
        )

    return message


async def get_account_by_phone_number_id(session: AsyncSession, phone_number_id: str) -> WhatsAppAccount | None:
    stmt = select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == phone_number_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
