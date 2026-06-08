import uuid

import httpx
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.config import settings
from app.db.session import get_db_session
from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.schemas.whatsapp import (
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    WhatsAppAccountConnectRequest,
    WhatsAppAccountResponse,
)
from app.services import conversation_service
from app.services.encryption import decrypt_secret, encrypt_secret
from app.services.whatsapp_client import WhatsAppApiError, WhatsAppClient

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# NOTE: `business_id` below stands in for the `OrganizationContext` dependency
# (`get_current_organization`) defined in the auth module — these endpoints are
# `member`/`admin` gated per `07-api-endpoints-reference.md`. Wired here as a
# plain UUID path/body value to keep this module independently reviewable; swap
# for the real dependency when the auth module lands.


@router.post("/{business_id}/connect", response_model=WhatsAppAccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_whatsapp_account(
    business_id: uuid.UUID,
    payload: WhatsAppAccountConnectRequest,
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppAccount:
    """Connect a WhatsApp Business number: validate the token against the Graph
    API, persist the (encrypted) credentials, and mark the account connected.
    """
    phone_number = await _fetch_and_verify_phone_number(payload.phone_number_id, payload.access_token)

    account = WhatsAppAccount(
        business_id=business_id,
        display_name=payload.display_name,
        phone_number=phone_number,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        access_token=encrypt_secret(payload.access_token),
        status="connected",
        connected_at=_utcnow(),
    )
    session.add(account)
    await session.flush()
    await session.refresh(account)
    return account


@router.get("/{business_id}/accounts", response_model=list[WhatsAppAccountResponse])
async def list_whatsapp_accounts(
    business_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> list[WhatsAppAccount]:
    stmt = select(WhatsAppAccount).where(WhatsAppAccount.business_id == business_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/{business_id}/accounts/{account_id}/disconnect", response_model=WhatsAppAccountResponse)
async def disconnect_whatsapp_account(
    business_id: uuid.UUID, account_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> WhatsAppAccount:
    account = await _get_account_or_404(session, business_id, account_id)
    account.status = "disconnected"
    account.access_token = None
    await session.flush()
    await session.refresh(account)
    return account


@router.post(
    "/{business_id}/accounts/{account_id}/send",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    business_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: SendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SendMessageResponse:
    """Send an outbound message through a connected number and persist it.

    Conversations are looked up by `(account_id, to)` — sending to a brand-new
    number is allowed (e.g. proactive outreach) and creates the thread.
    """
    account = await _get_account_or_404(session, business_id, account_id)
    if account.status != "connected" or not account.access_token:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="WhatsApp account is not connected")

    _validate_send_payload(payload)

    client = WhatsAppClient(phone_number_id=account.phone_number_id, access_token=decrypt_secret(account.access_token))

    try:
        if payload.message_type == "text":
            api_response = await client.send_text_message(payload.to, payload.text or "")
        elif payload.message_type == "image":
            api_response = await client.send_image_message(payload.to, payload.media_url or "", payload.caption)
        else:
            api_response = await client.send_document_message(
                payload.to, payload.media_url or "", payload.filename, payload.caption
            )
    except WhatsAppApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="WhatsApp API rejected the message") from exc

    whatsapp_message_id = api_response["messages"][0]["id"]

    from app.schemas.whatsapp import WebhookContact

    conversation = await conversation_service.get_or_create_conversation(
        session,
        business_id=business_id,
        whatsapp_account_id=account.id,
        contact=WebhookContact(wa_id=payload.to),
    )
    message = await conversation_service.store_outbound_message(
        session,
        business_id=business_id,
        conversation_id=conversation.id,
        sender_type="agent",
        message_type=payload.message_type,
        content=payload.text or payload.caption,
        media_url=payload.media_url,
        whatsapp_message_id=whatsapp_message_id,
    )

    return SendMessageResponse(message_id=message.id, whatsapp_message_id=whatsapp_message_id, status=message.status)


@router.get("/{business_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(business_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.business_id == business_id)
        .order_by(Conversation.last_message_at.desc().nulls_last())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{business_id}/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    business_id: uuid.UUID, conversation_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> list[Message]:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# --- Helpers -------------------------------------------------------------------


def _validate_send_payload(payload: SendMessageRequest) -> None:
    if payload.message_type == "text" and not payload.text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="`text` is required for text messages")
    if payload.message_type in ("image", "document") and not payload.media_url:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="`media_url` is required for image/document messages"
        )


async def _get_account_or_404(session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID) -> WhatsAppAccount:
    account = await session.get(WhatsAppAccount, account_id)
    if account is None or account.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="WhatsApp account not found")
    return account


async def _fetch_and_verify_phone_number(phone_number_id: str, access_token: str) -> str:
    """Confirm the supplied token can actually read this phone number before
    persisting it — surfaces bad-credential errors at connect time, not on the
    first send."""
    url = f"{settings.whatsapp_graph_api_url}/{phone_number_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {access_token}"}, params={"fields": "display_phone_number"})

    if response.is_error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not verify the WhatsApp phone number with the supplied access token",
        )
    return response.json().get("display_phone_number", "")


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc)
