import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.whatsapp import Conversation, Message, WhatsAppAccount
from app.services import conversation_service, operator_alert_service, sales_agent_service
from app.services.billing_service import (
    SubscriptionInactive,
    UsageLimitExceeded,
    check_usage_limit,
    increment_usage,
)
from app.services.encryption import decrypt_secret
from app.services.whatsapp_client import WhatsAppApiError, WhatsAppClient
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Recent turns fed to the LLM as conversation history (oldest first).
_HISTORY_LIMIT = 20

# Persistent event loop reused across tasks in the same worker process.
# Creating a new loop per task via asyncio.run() has overhead from loop setup
# and teardown; reusing the process-local loop is significantly faster.
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


@celery_app.task(name="agent.generate_and_send_reply", bind=True, max_retries=3, default_retry_delay=10)
def generate_and_send_reply(self, *, conversation_id: str, inbound_message_id: str) -> None:
    """Generate a sales-agent reply for a freshly-stored inbound message and send it.

    Runs off the webhook's request path (see app/webhooks/whatsapp.py) so a
    slow LLM/Graph-API round trip never risks Meta treating the webhook as
    unhealthy and disabling the subscription.
    """
    try:
        _get_worker_loop().run_until_complete(
            _generate_and_send_reply(uuid.UUID(conversation_id), uuid.UUID(inbound_message_id))
        )
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

    # Handoff guard. Once a human has taken over (`handoff`) or the thread is
    # `closed`, the AI must not speak — no LLM, no WhatsApp send, no system
    # note (operator already owns the conversation; a note would be noise).
    if conversation.status in ("handoff", "closed"):
        logger.info(
            "AI reply suppressed — conversation_id=%s status=%s",
            conversation_id,
            conversation.status,
        )
        return

    account = await session.get(WhatsAppAccount, conversation.whatsapp_account_id)
    if account is None or not account.access_token:
        logger.warning("No connected WhatsApp account for conversation_id=%s — skipping agent reply", conversation_id)
        return

    try:
        await check_usage_limit(session, business_id=conversation.business_id)
    except SubscriptionInactive as exc:
        logger.warning(
            "AI reply suppressed — subscription %s (business_id=%s)",
            exc.status,
            conversation.business_id,
        )
        await conversation_service.store_system_message(
            session,
            business_id=conversation.business_id,
            conversation_id=conversation.id,
            content=(
                f"AI reply was not sent: subscription is {exc.status}. "
                "Reactivate billing to resume automated replies."
            ),
        )
        return
    except UsageLimitExceeded as exc:
        logger.info("AI reply suppressed — %s (business_id=%s)", exc, conversation.business_id)
        return

    agent = await sales_agent_service.get_active_agent(session, business_id=conversation.business_id)
    if agent is None:
        logger.info("No active sales agent configured for business_id=%s — skipping", conversation.business_id)
        return

    # 24-hour service window gate. AI replies are always free-form; outside the
    # window Meta will reject them with error 131047 and (worse) doing so risks
    # the number's quality rating. Per Phase B decisions: do not send, do not
    # queue retry, do not attempt a delayed send — just record an operator-
    # visible system note so the inbox surfaces a missed reply.
    last_inbound_at = await conversation_service.get_last_inbound_at(session, conversation_id)
    if not conversation_service.is_within_service_window(last_inbound_at):
        logger.warning(
            "AI reply suppressed — conversation_id=%s outside 24h service window (last_inbound_at=%s)",
            conversation_id,
            last_inbound_at,
        )
        await conversation_service.store_system_message(
            session,
            business_id=conversation.business_id,
            conversation_id=conversation.id,
            content=(
                "AI reply was not sent: the contact's 24-hour customer service window has closed. "
                "Send an approved template to re-engage."
            ),
        )
        return

    # Idempotency gate (P0.4). Reserve a row keyed on inbound_message_id
    # BEFORE any LLM call or WhatsApp send, then commit so a concurrent retry
    # (Celery's auto-retry on transient failure) sees the marker and bails
    # out. The UNIQUE constraint on ai_interactions.inbound_message_id is
    # what makes the ON CONFLICT race-safe — without it, two parallel inserts
    # could both succeed and produce duplicate replies to the contact.
    reservation_id = await sales_agent_service.reserve_interaction(
        session,
        agent=agent,
        conversation_id=conversation.id,
        inbound_message_id=inbound_message.id,
    )
    if reservation_id is None:
        logger.info(
            "AI reply suppressed — interaction already exists for inbound_message_id=%s",
            inbound_message_id,
        )
        return
    # Commit the reservation marker independently so a later failure (and
    # rollback of the in-flight transaction) cannot erase it. Subsequent
    # writes in this turn go into a fresh autobegun transaction.
    await session.commit()

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
    except WhatsAppApiError as exc:
        logger.exception("Failed to send agent reply via WhatsApp for conversation_id=%s", conversation_id)
        # Surface to operators via the alert inbox. The reservation row already
        # exists, so a Celery retry will short-circuit at reserve_interaction —
        # the alert is the only way a human learns this contact got no reply.
        await operator_alert_service.create_alert(
            session,
            business_id=conversation.business_id,
            conversation_id=conversation.id,
            message_id=inbound_message.id,
            kind=operator_alert_service.ALERT_KIND_SEND_FAILED,
            title="WhatsApp send failed",
            body=f"AI reply could not be delivered (status={exc.status_code}). Contact may need a manual reply.",
        )
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

    await sales_agent_service.finalize_interaction(
        session,
        interaction_id=reservation_id,
        outbound_message_id=outbound_message.id,
        result=result,
    )

    await increment_usage(session, business_id=conversation.business_id)


async def _recent_messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(reversed(rows))
