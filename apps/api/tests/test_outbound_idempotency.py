"""Tests for outbound idempotency / duplicate-send prevention (P0.4).

A single inbound WhatsApp message must never generate more than one AI reply,
even when Celery retries after a transient DB / network failure. The contract:

  1. _run_turn reserves an ai_interactions row BEFORE the LLM call or send.
  2. Reservation uses INSERT ... ON CONFLICT DO NOTHING against the UNIQUE
     constraint on inbound_message_id (migration 20260612000001).
  3. On reservation success, _run_turn commits immediately so a concurrent
     retry sees the marker.
  4. On reservation failure (row already exists), _run_turn returns early —
     no LLM, no WhatsApp send.
  5. After a successful send, finalize_interaction fills in tokens / latency
     / chunks on the reserved row — no second insert.
"""

import re
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_BUSINESS_ID

CONVERSATION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
MESSAGE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ACCOUNT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
AGENT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
RESERVATION_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
OUTBOUND_MSG_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _conversation() -> MagicMock:
    conv = MagicMock()
    conv.id = CONVERSATION_ID
    conv.business_id = TEST_BUSINESS_ID
    conv.whatsapp_account_id = ACCOUNT_ID
    conv.contact_phone = "15551234567"
    conv.status = "open"
    return conv


def _inbound() -> MagicMock:
    m = MagicMock()
    m.id = MESSAGE_ID
    m.content = "hi"
    return m


def _account() -> MagicMock:
    a = MagicMock()
    a.id = ACCOUNT_ID
    a.business_id = TEST_BUSINESS_ID
    a.phone_number_id = "1234567890"
    a.access_token = "encrypted-token"
    return a


def _agent() -> MagicMock:
    a = MagicMock()
    a.id = AGENT_ID
    a.business_id = TEST_BUSINESS_ID
    a.provider = "anthropic"
    a.model = "claude-sonnet-4-5"
    return a


def _reply_result() -> MagicMock:
    r = MagicMock()
    r.reply = "hello there"
    r.prompt_tokens = 10
    r.completion_tokens = 5
    r.latency_ms = 123
    r.retrieved_chunks = []
    r.extracted_lead_fields = {}
    return r


# ---------------------------------------------------------------------------
# _run_turn integration
# ---------------------------------------------------------------------------


async def test_first_execution_reserves_and_proceeds():
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[_conversation(), _inbound(), _account()])
    session.commit = AsyncMock()

    reserve = AsyncMock(return_value=RESERVATION_ID)
    finalize = AsyncMock()
    send_text = AsyncMock(return_value={"messages": [{"id": "wamid.X"}]})
    outbound_msg = MagicMock(id=OUTBOUND_MSG_ID)

    with (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=_agent())),
        patch.object(
            agent_tasks.conversation_service,
            "get_last_inbound_at",
            new=AsyncMock(return_value=None),
        ),
        patch.object(agent_tasks.conversation_service, "is_within_service_window", return_value=True),
        patch.object(agent_tasks.sales_agent_service, "reserve_interaction", new=reserve),
        patch.object(agent_tasks.sales_agent_service, "finalize_interaction", new=finalize),
        patch.object(
            agent_tasks.sales_agent_service,
            "generate_agent_reply",
            new=AsyncMock(return_value=_reply_result()),
        ),
        patch.object(agent_tasks, "_recent_messages", new=AsyncMock(return_value=[])),
        patch.object(agent_tasks, "decrypt_secret", return_value="plain-token"),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(
            agent_tasks.conversation_service,
            "store_outbound_message",
            new=AsyncMock(return_value=outbound_msg),
        ),
        patch.object(agent_tasks, "increment_usage", new=AsyncMock()),
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    reserve.assert_awaited_once()
    # Reservation must be committed before LLM / send so a concurrent retry sees it.
    session.commit.assert_awaited()
    send_text.assert_awaited_once()
    finalize.assert_awaited_once()
    # Confirm finalize received the reservation_id (no second insert path).
    assert finalize.await_args.kwargs["interaction_id"] == RESERVATION_ID
    assert finalize.await_args.kwargs["outbound_message_id"] == OUTBOUND_MSG_ID


async def test_duplicate_execution_exits_early_no_llm_no_send():
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[_conversation(), _inbound(), _account()])
    session.commit = AsyncMock()

    reserve = AsyncMock(return_value=None)  # conflict — row exists
    finalize = AsyncMock()
    gen_reply = AsyncMock()
    send_text = AsyncMock()

    with (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=_agent())),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock(return_value=None)),
        patch.object(agent_tasks.conversation_service, "is_within_service_window", return_value=True),
        patch.object(agent_tasks.sales_agent_service, "reserve_interaction", new=reserve),
        patch.object(agent_tasks.sales_agent_service, "finalize_interaction", new=finalize),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=gen_reply),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    reserve.assert_awaited_once()
    gen_reply.assert_not_called()
    send_text.assert_not_called()
    finalize.assert_not_called()
    # No commit on the duplicate path — the in-flight transaction is empty
    # and the wrapping _generate_and_send_reply handles the (no-op) commit.
    session.commit.assert_not_called()


async def test_send_called_exactly_once_across_two_executions():
    """Simulate a Celery retry: first call reserves and sends; second call
    finds the reservation and bails. WhatsApp send fires exactly once."""
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppClient

    send_text = AsyncMock(return_value={"messages": [{"id": "wamid.X"}]})
    finalize = AsyncMock()
    gen_reply = AsyncMock(return_value=_reply_result())
    outbound_msg = MagicMock(id=OUTBOUND_MSG_ID)

    # First execution: reserve returns id. Second: returns None.
    reserve = AsyncMock(side_effect=[RESERVATION_ID, None])

    common_patches = (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=_agent())),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock(return_value=None)),
        patch.object(agent_tasks.conversation_service, "is_within_service_window", return_value=True),
        patch.object(agent_tasks.sales_agent_service, "reserve_interaction", new=reserve),
        patch.object(agent_tasks.sales_agent_service, "finalize_interaction", new=finalize),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=gen_reply),
        patch.object(agent_tasks, "_recent_messages", new=AsyncMock(return_value=[])),
        patch.object(agent_tasks, "decrypt_secret", return_value="plain-token"),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(
            agent_tasks.conversation_service,
            "store_outbound_message",
            new=AsyncMock(return_value=outbound_msg),
        ),
        patch.object(agent_tasks, "increment_usage", new=AsyncMock()),
    )

    for _ in range(2):
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[_conversation(), _inbound(), _account()])
        session.commit = AsyncMock()
        with common_patches[0], common_patches[1], common_patches[2], common_patches[3], \
             common_patches[4], common_patches[5], common_patches[6], common_patches[7], \
             common_patches[8], common_patches[9], common_patches[10], common_patches[11]:
            await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    assert reserve.await_count == 2
    assert send_text.await_count == 1, "duplicate send across retry"
    assert gen_reply.await_count == 1, "duplicate LLM call across retry"
    assert finalize.await_count == 1


async def test_retry_after_send_failure_does_not_duplicate_interaction():
    """If WhatsApp send raises, the turn exits without finalize. A retry hits
    the existing reservation row → reserve returns None → no second send,
    no second finalize. Net effect: one reserved row, zero sends — the
    operator-alerting layer (P0.2) will surface the failure."""
    from app.workers.tasks import agent_tasks
    from app.services.whatsapp_client import WhatsAppApiError, WhatsAppClient

    finalize = AsyncMock()
    gen_reply = AsyncMock(return_value=_reply_result())
    # First send raises, second attempt never happens because reserve denies it.
    send_text = AsyncMock(side_effect=WhatsAppApiError(503, {"error": "network blip"}))
    reserve = AsyncMock(side_effect=[RESERVATION_ID, None])

    common_patches = (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=_agent())),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock(return_value=None)),
        patch.object(agent_tasks.conversation_service, "is_within_service_window", return_value=True),
        patch.object(agent_tasks.sales_agent_service, "reserve_interaction", new=reserve),
        patch.object(agent_tasks.sales_agent_service, "finalize_interaction", new=finalize),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=gen_reply),
        patch.object(agent_tasks, "_recent_messages", new=AsyncMock(return_value=[])),
        patch.object(agent_tasks, "decrypt_secret", return_value="plain-token"),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
    )

    for _ in range(2):
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[_conversation(), _inbound(), _account()])
        session.commit = AsyncMock()
        with common_patches[0], common_patches[1], common_patches[2], common_patches[3], \
             common_patches[4], common_patches[5], common_patches[6], common_patches[7], \
             common_patches[8], common_patches[9]:
            await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    assert reserve.await_count == 2
    assert send_text.await_count == 1  # second attempt bails at reservation
    finalize.assert_not_called()  # neither attempt finishes the happy path


# ---------------------------------------------------------------------------
# Migration shape — validate dedupe + unique-constraint logic statically.
# ---------------------------------------------------------------------------


def test_migration_dedupes_then_adds_constraint():
    """Sanity-check the migration is well-formed: it MUST dedupe before
    adding the unique constraint, otherwise the ALTER TABLE blows up on any
    existing duplicate rows."""
    path = (
        Path(__file__).resolve().parents[3]
        / "supabase"
        / "migrations"
        / "20260612000001_ai_interactions_inbound_unique.sql"
    )
    sql = path.read_text()

    dedupe_pos = sql.lower().find("delete from ai_interactions")
    constraint_pos = sql.lower().find("add constraint ux_ai_interactions_inbound_message_id")
    assert dedupe_pos != -1, "migration missing dedupe step"
    assert constraint_pos != -1, "migration missing unique constraint"
    assert dedupe_pos < constraint_pos, "dedupe must run before constraint creation"

    # Idempotency: constraint addition must be guarded by an existence check.
    assert re.search(
        r"if not exists\s*\(\s*select\s+1\s+from\s+pg_constraint",
        sql,
        re.IGNORECASE,
    ), "constraint addition not wrapped in idempotent guard"

    # Dedupe must key on inbound_message_id and keep MIN(id).
    assert "min(id)" in sql.lower()
    assert "group by inbound_message_id" in sql.lower()
