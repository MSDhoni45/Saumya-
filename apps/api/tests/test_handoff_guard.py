"""Tests for the handoff guard in agent_tasks._run_turn.

P0.1 — when a human operator has taken over a conversation (`status="handoff"`)
or the thread is `closed`, the AI must stay silent: no LLM call, no WhatsApp
send, and no system note (operator already owns the inbox; a note would be
noise). Any other status proceeds through the existing pipeline.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_BUSINESS_ID

CONVERSATION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
MESSAGE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ACCOUNT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _conversation(status: str) -> MagicMock:
    conv = MagicMock()
    conv.id = CONVERSATION_ID
    conv.business_id = TEST_BUSINESS_ID
    conv.whatsapp_account_id = ACCOUNT_ID
    conv.contact_phone = "15551234567"
    conv.status = status
    return conv


def _inbound() -> MagicMock:
    m = MagicMock()
    m.id = MESSAGE_ID
    return m


def _account() -> MagicMock:
    a = MagicMock()
    a.id = ACCOUNT_ID
    a.business_id = TEST_BUSINESS_ID
    a.phone_number_id = "1234567890"
    a.access_token = "encrypted-token"
    return a


async def _assert_silent(status: str) -> None:
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    session = AsyncMock()
    # Only conversation + inbound are fetched before the guard returns.
    session.get = AsyncMock(side_effect=[_conversation(status), _inbound()])

    store_system = AsyncMock()
    send_text = AsyncMock()
    check_usage = AsyncMock()
    gen_reply = AsyncMock()
    get_agent = AsyncMock()

    with (
        patch.object(agent_tasks, "check_usage_limit", new=check_usage),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=get_agent),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=gen_reply),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=store_system),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock()),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    # Guard fires before account fetch, billing, LLM, send, system note.
    check_usage.assert_not_called()
    get_agent.assert_not_called()
    gen_reply.assert_not_called()
    send_text.assert_not_called()
    store_system.assert_not_called()


async def test_handoff_suppresses_everything():
    await _assert_silent("handoff")


async def test_closed_suppresses_everything():
    await _assert_silent("closed")


async def test_open_conversation_proceeds_to_account_fetch():
    """Any non-blocking status must continue past the guard. We verify by
    letting the next step (account fetch returns None → early return with a
    warning) run — that proves the guard didn't short-circuit."""
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    session = AsyncMock()
    # conversation (open) → inbound → account (None triggers next early return)
    session.get = AsyncMock(side_effect=[_conversation("open"), _inbound(), None])

    check_usage = AsyncMock()
    gen_reply = AsyncMock()
    send_text = AsyncMock()
    store_system = AsyncMock()

    with (
        patch.object(agent_tasks, "check_usage_limit", new=check_usage),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=gen_reply),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=store_system),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock()),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    # session.get was called 3 times → we got past the guard into account fetch.
    assert session.get.await_count == 3
    # The account-missing branch returns before usage/LLM/send.
    check_usage.assert_not_called()
    gen_reply.assert_not_called()
    send_text.assert_not_called()
    store_system.assert_not_called()
