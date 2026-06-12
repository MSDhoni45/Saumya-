"""Tests for the subscription-state gate that suppresses AI replies.

P0.3 — before this fix, `check_usage_limit` returned early for any subscription
status outside `("active", "trialing")`, which meant a `paused` or `cancelled`
subscription silently bypassed the usage check and the bot kept replying. The
gate now raises `SubscriptionInactive` for explicitly blocking states and lets
`past_due` through (Stripe-style: service continues during dunning until the
subscription is actually cancelled).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import billing_service
from app.services.billing_service import (
    SubscriptionInactive,
    UsageLimitExceeded,
    check_usage_limit,
)

from tests.conftest import TEST_BUSINESS_ID

CONVERSATION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
MESSAGE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ACCOUNT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _sub(status: str, plan: str = "starter") -> MagicMock:
    sub = MagicMock()
    sub.status = status
    sub.plan = plan
    return sub


def _usage(count: int = 0) -> MagicMock:
    usage = MagicMock()
    usage.message_count = count
    return usage


# ---------------------------------------------------------------------------
# Unit: check_usage_limit honours subscription state
# ---------------------------------------------------------------------------


async def test_paused_subscription_raises_subscription_inactive():
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("paused"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(0))),
    ):
        with pytest.raises(SubscriptionInactive) as exc_info:
            await check_usage_limit(session, business_id=TEST_BUSINESS_ID)

    assert exc_info.value.status == "paused"


async def test_cancelled_subscription_raises_subscription_inactive():
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("cancelled"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(0))),
    ):
        with pytest.raises(SubscriptionInactive) as exc_info:
            await check_usage_limit(session, business_id=TEST_BUSINESS_ID)

    assert exc_info.value.status == "cancelled"


async def test_past_due_subscription_passes_through():
    """Stripe-style: dunning leaves the subscription functional."""
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("past_due"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(0))),
    ):
        # Should complete without raising.
        await check_usage_limit(session, business_id=TEST_BUSINESS_ID)


async def test_active_subscription_under_limit_passes():
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("active"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(0))),
    ):
        await check_usage_limit(session, business_id=TEST_BUSINESS_ID)


async def test_trialing_subscription_passes():
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("trialing"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(0))),
    ):
        await check_usage_limit(session, business_id=TEST_BUSINESS_ID)


async def test_active_subscription_at_limit_raises_usage_limit_exceeded():
    """Order-of-evaluation lock-in: blocking-state check must precede usage check,
    but an active subscription at-cap still raises the usage error."""
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("active", plan="starter"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(10_000_000))),
    ):
        with pytest.raises(UsageLimitExceeded):
            await check_usage_limit(session, business_id=TEST_BUSINESS_ID)


async def test_paused_subscription_blocks_before_usage_check():
    """If both a usage cap *and* a blocking status apply, the blocking status
    is reported — it's the more actionable failure mode for the operator."""
    session = AsyncMock()
    with (
        patch.object(billing_service, "get_or_create_subscription", AsyncMock(return_value=_sub("paused", plan="starter"))),
        patch.object(billing_service, "get_current_usage", AsyncMock(return_value=_usage(10_000_000))),
    ):
        with pytest.raises(SubscriptionInactive):
            await check_usage_limit(session, business_id=TEST_BUSINESS_ID)


# ---------------------------------------------------------------------------
# Worker integration: _run_turn suppresses + writes system note
# ---------------------------------------------------------------------------


def _connected_account() -> MagicMock:
    account = MagicMock()
    account.id = ACCOUNT_ID
    account.business_id = TEST_BUSINESS_ID
    account.phone_number_id = "1234567890"
    account.access_token = "encrypted-token"
    return account


async def test_run_turn_paused_subscription_writes_system_note_and_skips_send():
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    conversation = MagicMock()
    conversation.id = CONVERSATION_ID
    conversation.business_id = TEST_BUSINESS_ID
    conversation.whatsapp_account_id = ACCOUNT_ID
    conversation.contact_phone = "15551234567"

    inbound = MagicMock()
    inbound.id = MESSAGE_ID

    account = _connected_account()

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[conversation, inbound, account])

    store_system = AsyncMock()
    send_text = AsyncMock()

    with (
        patch.object(
            agent_tasks,
            "check_usage_limit",
            new=AsyncMock(side_effect=billing_service.SubscriptionInactive(status="paused")),
        ),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock()),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=store_system),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock()),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=AsyncMock()) as gen,
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    gen.assert_not_called()
    send_text.assert_not_called()
    store_system.assert_awaited_once()
    # The system note must name the blocking status so operators can act on it.
    call_kwargs = store_system.await_args.kwargs
    assert "paused" in call_kwargs["content"]
    assert call_kwargs["business_id"] == TEST_BUSINESS_ID
    assert call_kwargs["conversation_id"] == CONVERSATION_ID


async def test_run_turn_cancelled_subscription_writes_system_note():
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    conversation = MagicMock()
    conversation.id = CONVERSATION_ID
    conversation.business_id = TEST_BUSINESS_ID
    conversation.whatsapp_account_id = ACCOUNT_ID
    conversation.contact_phone = "15551234567"

    inbound = MagicMock()
    inbound.id = MESSAGE_ID

    account = _connected_account()
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[conversation, inbound, account])

    store_system = AsyncMock()
    send_text = AsyncMock()

    with (
        patch.object(
            agent_tasks,
            "check_usage_limit",
            new=AsyncMock(side_effect=billing_service.SubscriptionInactive(status="cancelled")),
        ),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock()),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=store_system),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock()),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=AsyncMock()) as gen,
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    gen.assert_not_called()
    send_text.assert_not_called()
    store_system.assert_awaited_once()
    assert "cancelled" in store_system.await_args.kwargs["content"]


async def test_run_turn_usage_limit_does_not_write_system_note():
    """Usage-cap suppression is intentionally quieter than subscription-state
    suppression: the operator already sees usage in the billing UI, and a
    system note per inbound during a cap-hit storm would spam the inbox."""
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    conversation = MagicMock()
    conversation.id = CONVERSATION_ID
    conversation.business_id = TEST_BUSINESS_ID
    conversation.whatsapp_account_id = ACCOUNT_ID
    conversation.contact_phone = "15551234567"

    inbound = MagicMock()
    inbound.id = MESSAGE_ID

    account = _connected_account()
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[conversation, inbound, account])

    store_system = AsyncMock()
    send_text = AsyncMock()

    with (
        patch.object(
            agent_tasks,
            "check_usage_limit",
            new=AsyncMock(side_effect=billing_service.UsageLimitExceeded(plan="starter", limit=1000)),
        ),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock()),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=store_system),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock()),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=AsyncMock()) as gen,
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    gen.assert_not_called()
    send_text.assert_not_called()
    store_system.assert_not_called()
