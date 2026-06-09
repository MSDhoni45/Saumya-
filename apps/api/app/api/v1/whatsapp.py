import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.schemas.whatsapp import (
    ConversationResponse,
    ConversationUpdateRequest,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    WhatsAppAccountConnectRequest,
    WhatsAppAccountResponse,
)
from app.services import conversation_service
from app.services.encryption import decrypt_secret, encrypt_secret
from app.services.realtime import publish_new_message, stream_conversation
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

    # Flush so the message has DB-assigned fields (id, created_at) before we
    # serialize it for the SSE broadcast below.
    await session.flush()
    await session.refresh(message)

    # Notify any open SSE stream for this thread — this is best-effort (see
    # publish_new_message's error-swallowing contract), so we fire it before the
    # HTTP response but after the DB flush so consumers see a committed row.
    await publish_new_message(str(conversation.id), MessageResponse.model_validate(message).model_dump(mode="json"))

    return SendMessageResponse(message_id=message.id, whatsapp_message_id=whatsapp_message_id, status=message.status)


@router.get("/{business_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    business_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> list[ConversationResponse]:
    # Correlated subqueries pull the most-recent message's content and sender
    # type for each conversation in a single round-trip rather than N+1 queries.
    last_content_subq = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    last_sender_subq = (
        select(Message.sender_type)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )

    stmt = (
        select(
            Conversation,
            last_content_subq.label("last_message_content"),
            last_sender_subq.label("last_sender_type"),
        )
        .where(Conversation.business_id == business_id)
        .order_by(Conversation.last_message_at.desc().nulls_last())
    )
    rows = (await session.execute(stmt)).all()

    responses: list[ConversationResponse] = []
    for row in rows:
        resp = ConversationResponse.model_validate(row.Conversation)
        resp.last_message_content = row.last_message_content
        resp.last_sender_type = row.last_sender_type
        responses.append(resp)
    return responses


@router.patch("/{business_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Conversation:
    """Update a conversation's status and/or assignment.

    Backs the inbox's human-takeover flow: claiming a conversation sets
    `status="handoff"` + `assigned_user_id`, hand-back clears both, and
    reassignment changes `assigned_user_id` alone. `assigned_user_id` is only
    touched when the client explicitly includes it (so a status-only update
    can't accidentally clear an existing assignment) — `None` clears it.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    fields_set = payload.model_fields_set
    if "status" in fields_set and payload.status is not None:
        conversation.status = payload.status
    if "assigned_user_id" in fields_set:
        conversation.assigned_user_id = payload.assigned_user_id

    await session.flush()
    await session.refresh(conversation)
    return conversation


@router.get("/{business_id}/conversations/{conversation_id}/stream")
async def stream_conversation_messages(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Server-Sent Events stream for real-time message delivery.

    The browser connects once per open conversation thread; new messages arrive
    as `data:` lines (JSON-encoded MessageResponse) without the overhead of
    polling. Falls back to the polling layer automatically if the connection
    drops — see `useMessageStream` in the frontend.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return StreamingResponse(
        stream_conversation(str(conversation_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for streaming
            "Connection": "keep-alive",
        },
    )


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
