import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.services import conversation_service, sales_agent_service
from app.services.encryption import decrypt_secret
from app.services.whatsapp_client import WhatsAppApiError, WhatsAppClient
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Recent turns fed to the LLM as conversation history (oldest first).
_HISTORY_LIMIT = 20


@celery_app.task(name="agent.generate_and_send_reply", bind=True, max_retries=3, default_retry_delay=10)
def generate_and_send_reply(self, *, conversation_id: str, inbound_message_id: str) -> None:
    """Generate a sales-agent reply for a freshly-stored inbound message and send it.

    Runs off the webhook's request path (see app/webhooks/whatsapp.py) so a
    slow LLM/Graph-API round trip never risks Meta treating the webhook as
    unhealthy and disabling the subscription.
    """
    try:
        asyncio.run(_generate_and_send_reply(uuid.UUID(conversation_id), uuid.UUID(inbound_message_id)))
    except Exception as exc:  # noqa: BLE001 - retry on anything transient; Celery logs the traceback
        logger.exception(
            "Agent reply generation failed for conversation_id=%s inbound_message_id=%s",
            conversation_id,
            inbound_message_id,
        )
        raise self.retry(exc=exc) from exc


async def _generate_and_send_reply(conversation_id: uuid.UUID, inbound_message_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        try:
            await _run_turn(session, conversation_id, inbound_message_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _run_turn(session: AsyncSession, conversation_id: uuid.UUID, inbound_message_id: uuid.UUID) -> None:
    conversation = await session.get(Conversation, conversation_id)
    inbound_message = await session.get(Message, inbound_message_id)
    if conversation is None or inbound_message is None:
        logger.warning("Conversation or inbound message missing (conversation_id=%s)", conversation_id)
        return

    account = await session.get(WhatsAppAccount, conversation.whatsapp_account_id)
    if account is None or not account.access_token:
        logger.warning("No connected WhatsApp account for conversation_id=%s — skipping agent reply", conversation_id)
        return

    agent = await sales_agent_service.get_active_agent(session, business_id=conversation.business_id)
    if agent is None:
        logger.info("No active sales agent configured for business_id=%s — skipping", conversation.business_id)
        return

    history_messages = await _recent_messages(session, conversation_id)

    result = await sales_agent_service.generate_agent_reply(
        session,
        agent=agent,
        conversation=conversation,
        inbound_message=inbound_message,
        history_messages=history_messages,
    )

    client = WhatsAppClient(phone_number_id=account.phone_number_id, access_token=decrypt_secret(account.access_token))
    try:
        send_response = await client.send_text_message(to=conversation.contact_phone, body=result.reply)
    except WhatsAppApiError:
        logger.exception("Failed to send agent reply via WhatsApp for conversation_id=%s", conversation_id)
        return

    outbound_message = await conversation_service.store_outbound_message(
        session,
        business_id=conversation.business_id,
        conversation_id=conversation.id,
        sender_type="ai",
        message_type="text",
        content=result.reply,
        media_url=None,
        whatsapp_message_id=send_response["messages"][0]["id"],
    )

    await sales_agent_service.record_interaction(
        session,
        agent=agent,
        conversation_id=conversation.id,
        inbound_message_id=inbound_message.id,
        outbound_message_id=outbound_message.id,
        result=result,
    )


async def _recent_messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(reversed(rows))
