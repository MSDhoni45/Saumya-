import math
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.core.config import settings
from app.db.session import get_db_session
from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.schemas.whatsapp import (
    ConversationResponse,
    ConversationUpdateRequest,
    MessageResponse,
    PaginatedConversations,
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


@router.post("/{business_id}/connect", response_model=WhatsAppAccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_whatsapp_account(
    business_id: uuid.UUID,
    payload: WhatsAppAccountConnectRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppAccount:
    """Connect a WhatsApp Business number: validate the token against the Graph
    API, persist the (encrypted) credentials, and mark the account connected.
    """
    require_business_access(ctx, business_id)
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
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[WhatsAppAccount]:
    require_business_access(ctx, business_id)
    stmt = select(WhatsAppAccount).where(WhatsAppAccount.business_id == business_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/{business_id}/accounts/{account_id}/disconnect", response_model=WhatsAppAccountResponse)
async def disconnect_whatsapp_account(
    business_id: uuid.UUID,
    account_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppAccount:
    require_business_access(ctx, business_id)
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
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> SendMessageResponse:
    """Send an outbound message through a connected number and persist it.

    Conversations are looked up by `(account_id, to)` — sending to a brand-new
    number is allowed (e.g. proactive outreach) and creates the thread.
    """
    require_business_access(ctx, business_id)
    account = await _get_account_or_404(session, business_id, account_id)
    if account.status != "connected" or not account.access_token:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="WhatsApp account is not connected")

    _validate_send_payload(payload)

    from app.schemas.whatsapp import WebhookContact

    # Resolve the conversation up-front so we can enforce the 24-hour service
    # window *before* hitting Meta — sending a free-form message past the
    # window would be rejected with error 131047 anyway, and we'd rather fail
    # fast with a structured 409 than burn a Graph API call.
    conversation = await conversation_service.get_or_create_conversation(
        session,
        business_id=business_id,
        whatsapp_account_id=account.id,
        contact=WebhookContact(wa_id=payload.to),
    )

    if payload.message_type != "template":
        last_inbound_at = await conversation_service.get_last_inbound_at(session, conversation.id)
        if not conversation_service.is_within_service_window(last_inbound_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "OUTSIDE_SERVICE_WINDOW",
                    "message": "Free-form WhatsApp messages are not allowed outside the 24-hour customer service window.",
                    "requires_template": True,
                },
            )

    client = WhatsAppClient(phone_number_id=account.phone_number_id, access_token=decrypt_secret(account.access_token))

    try:
        if payload.message_type == "text":
            api_response = await client.send_text_message(payload.to, payload.text or "")
        elif payload.message_type == "image":
            api_response = await client.send_image_message(payload.to, payload.media_url or "", payload.caption)
        elif payload.message_type == "template":
            api_response = await client.send_template_message(
                payload.to,
                payload.template_name or "",
                payload.language_code or "",
                payload.template_components,
            )
        else:
            api_response = await client.send_document_message(
                payload.to, payload.media_url or "", payload.filename, payload.caption
            )
    except WhatsAppApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="WhatsApp API rejected the message") from exc

    whatsapp_message_id = api_response["messages"][0]["id"]

    stored_content = (
        payload.template_name if payload.message_type == "template" else (payload.text or payload.caption)
    )
    message = await conversation_service.store_outbound_message(
        session,
        business_id=business_id,
        conversation_id=conversation.id,
        sender_type="agent",
        message_type=payload.message_type,
        content=stored_content,
        media_url=payload.media_url,
        whatsapp_message_id=whatsapp_message_id,
    )

    await session.flush()
    await session.refresh(message)

    await publish_new_message(str(conversation.id), MessageResponse.model_validate(message).model_dump(mode="json"))

    return SendMessageResponse(message_id=message.id, whatsapp_message_id=whatsapp_message_id, status=message.status)


_CONV_MAX_PAGE_SIZE = 100
_CONV_DEFAULT_PAGE_SIZE = 25


@router.get("/{business_id}/conversations", response_model=PaginatedConversations)
async def list_conversations(
    business_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status", description="Comma-separated status values, e.g. open,pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(_CONV_DEFAULT_PAGE_SIZE, ge=1, le=_CONV_MAX_PAGE_SIZE),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedConversations:
    require_business_access(ctx, business_id)
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

    base = select(Conversation).where(Conversation.business_id == business_id)
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
        if statuses:
            base = base.where(Conversation.status.in_(statuses))

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Conversation,
            last_content_subq.label("last_message_content"),
            last_sender_subq.label("last_sender_type"),
        )
        .where(Conversation.business_id == business_id)
        .order_by(Conversation.last_message_at.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(Conversation.status.in_(statuses))

    rows = (await session.execute(stmt)).all()

    items: list[ConversationResponse] = []
    for row in rows:
        resp = ConversationResponse.model_validate(row.Conversation)
        resp.last_message_content = row.last_message_content
        resp.last_sender_type = row.last_sender_type
        items.append(resp)

    return PaginatedConversations(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.patch("/{business_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> Conversation:
    """Update a conversation's status and/or assignment.

    Backs the inbox's human-takeover flow: claiming a conversation sets
    `status="handoff"` + `assigned_user_id`, hand-back clears both, and
    reassignment changes `assigned_user_id` alone. `assigned_user_id` is only
    touched when the client explicitly includes it (so a status-only update
    can't accidentally clear an existing assignment) — `None` clears it.
    """
    require_business_access(ctx, business_id)
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
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Server-Sent Events stream for real-time message delivery."""
    require_business_access(ctx, business_id)
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return StreamingResponse(
        stream_conversation(str(conversation_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{business_id}/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200, description="Number of messages to return"),
    before_id: uuid.UUID | None = Query(None, description="Return messages older than this message ID"),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[Message]:
    require_business_access(ctx, business_id)
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    stmt = select(Message).where(Message.conversation_id == conversation_id)

    if before_id is not None:
        anchor = await session.get(Message, before_id)
        if anchor is not None:
            stmt = stmt.where(Message.created_at < anchor.created_at)

    stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    # Return in ascending order so the UI can append naturally
    return list(reversed(rows))


# --- Helpers -------------------------------------------------------------------


def _validate_send_payload(payload: SendMessageRequest) -> None:
    if payload.message_type == "text" and not payload.text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="`text` is required for text messages")
    if payload.message_type in ("image", "document") and not payload.media_url:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="`media_url` is required for image/document messages"
        )
    if payload.message_type == "template" and (not payload.template_name or not payload.language_code):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="`template_name` and `language_code` are required for template messages",
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
