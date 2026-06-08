import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_whatsapp_webhook_handshake, verify_whatsapp_webhook_signature
from app.db.session import async_session_factory
from app.schemas.whatsapp import WebhookEnvelope, WebhookMediaPayload
from app.services import conversation_service
from app.services.encryption import decrypt_secret
from app.services.whatsapp_client import WhatsAppClient
from app.services.storage import upload_inbound_media

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])

_MEDIA_FIELDS = ("image", "document", "audio", "video")


@router.get("")
async def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Meta's one-time handshake when the webhook URL is registered.

    Must echo back `hub.challenge` as plain text with a 200 — anything else and
    Meta refuses to save the subscription.
    """
    if not verify_whatsapp_webhook_handshake(hub_mode, hub_verify_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed")
    return Response(content=hub_challenge or "", media_type="text/plain")


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    """Receive inbound WhatsApp events (messages, status updates).

    Always returns 200 quickly — Meta retries aggressively (with backoff that
    eventually disables the subscription) on non-2xx responses, so failures in
    *processing* a payload must never surface as a non-2xx here. Validation/
    signature failures are the one exception: those indicate the request isn't
    a legitimate Meta delivery at all.
    """
    raw_body = await request.body()

    if not verify_whatsapp_webhook_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        envelope = WebhookEnvelope.model_validate_json(raw_body)
    except ValidationError:
        logger.warning("Received malformed WhatsApp webhook payload", exc_info=True)
        return {"status": "ignored"}

    if envelope.object != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in envelope.entry:
        for change in entry.changes:
            if change.field != "messages" or not change.value.messages:
                continue
            await _process_message_change(change.value)

    return {"status": "received"}


async def _process_message_change(value) -> None:  # noqa: ANN001 - WebhookValue, kept loose to avoid import cycle in signature
    phone_number_id = value.metadata.phone_number_id
    contacts_by_wa_id = {c.wa_id: c for c in (value.contacts or [])}

    async with async_session_factory() as session:
        try:
            await _persist_inbound_messages(session, phone_number_id, contacts_by_wa_id, value.messages or [])
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to persist inbound WhatsApp messages for phone_number_id=%s", phone_number_id)
            # Swallow: re-raising would surface as a 500 to Meta and trigger
            # redelivery storms. The unique `whatsapp_message_id` index makes
            # redelivery (via Meta's own retries, or a future reprocessing job)
            # safe to retry from scratch.


async def _persist_inbound_messages(session: AsyncSession, phone_number_id, contacts_by_wa_id, messages) -> None:
    account = await conversation_service.get_account_by_phone_number_id(session, phone_number_id)
    if account is None:
        logger.warning("Webhook event for unknown phone_number_id=%s", phone_number_id)
        return

    client: WhatsAppClient | None = None
    if account.access_token:
        client = WhatsAppClient(phone_number_id=account.phone_number_id, access_token=decrypt_secret(account.access_token))

    for whatsapp_message in messages:
        contact = contacts_by_wa_id.get(whatsapp_message.from_)
        if contact is None:
            from app.schemas.whatsapp import WebhookContact

            contact = WebhookContact(wa_id=whatsapp_message.from_)

        conversation = await conversation_service.get_or_create_conversation(
            session,
            business_id=account.business_id,
            whatsapp_account_id=account.id,
            contact=contact,
        )

        media_url = None
        media_payload: WebhookMediaPayload | None = (
            whatsapp_message.image or whatsapp_message.document or whatsapp_message.audio or whatsapp_message.video
        )
        if media_payload and client is not None:
            try:
                media_url = await conversation_service.fetch_and_store_inbound_media(
                    session, client=client, media=media_payload, storage_uploader=upload_inbound_media
                )
            except Exception:
                logger.exception("Failed to fetch/store inbound media id=%s", media_payload.id)

        await conversation_service.store_inbound_message(
            session,
            business_id=account.business_id,
            conversation=conversation,
            whatsapp_message=whatsapp_message,
            media_url=media_url,
        )
