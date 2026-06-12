"""Tests for operator alerting (P0.2).

When the automated pipeline can't finish a turn, an OperatorAlert row must be
written and the SSE channel must publish — operators rely on this to know a
contact got no reply.
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.services import operator_alert_service
from tests.conftest import TEST_BUSINESS_ID, TEST_USER_ID

CONVERSATION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
MESSAGE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ACCOUNT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
AGENT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
RESERVATION_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
ALERT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


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
    r.reply = "hello"
    r.prompt_tokens = 10
    r.completion_tokens = 5
    r.latency_ms = 100
    r.retrieved_chunks = []
    r.extracted_lead_fields = {}
    return r


# ---------------------------------------------------------------------------
# WhatsAppApiError → alert
# ---------------------------------------------------------------------------


async def test_whatsapp_send_failure_creates_alert():
    from app.services.whatsapp_client import WhatsAppApiError, WhatsAppClient
    from app.workers.tasks import agent_tasks

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[_conversation(), _inbound(), _account()])
    session.commit = AsyncMock()

    create_alert = AsyncMock()
    send_text = AsyncMock(side_effect=WhatsAppApiError(503, {"error": "boom"}))

    with (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=_agent())),
        patch.object(agent_tasks.conversation_service, "get_last_inbound_at", new=AsyncMock(return_value=None)),
        patch.object(agent_tasks.conversation_service, "is_within_service_window", return_value=True),
        patch.object(agent_tasks.sales_agent_service, "reserve_interaction", new=AsyncMock(return_value=RESERVATION_ID)),
        patch.object(
            agent_tasks.sales_agent_service,
            "generate_agent_reply",
            new=AsyncMock(return_value=_reply_result()),
        ),
        patch.object(agent_tasks, "_recent_messages", new=AsyncMock(return_value=[])),
        patch.object(agent_tasks, "decrypt_secret", return_value="plain"),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(agent_tasks.operator_alert_service, "create_alert", new=create_alert),
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    create_alert.assert_awaited_once()
    kwargs = create_alert.await_args.kwargs
    assert kwargs["business_id"] == TEST_BUSINESS_ID
    assert kwargs["conversation_id"] == CONVERSATION_ID
    assert kwargs["message_id"] == MESSAGE_ID
    assert kwargs["kind"] == operator_alert_service.ALERT_KIND_SEND_FAILED


# ---------------------------------------------------------------------------
# Status callback `failed` → alert
# ---------------------------------------------------------------------------


async def test_status_failed_creates_alert():
    from app.schemas.whatsapp import WebhookStatus, WebhookStatusError
    from app.services import conversation_service

    message = MagicMock()
    message.id = MESSAGE_ID
    message.business_id = TEST_BUSINESS_ID
    message.conversation_id = CONVERSATION_ID
    message.status = "sent"
    message.error_code = None
    message.error_title = None

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=message)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    status_event = WebhookStatus(
        id="wamid.X",
        status="failed",
        timestamp="1700000000",
        recipient_id="15551234567",
        errors=[WebhookStatusError(code=131047, title="re-engagement", message=None)],
    )

    create_alert = AsyncMock()
    with patch.object(conversation_service.operator_alert_service, "create_alert", new=create_alert):
        out = await conversation_service.apply_message_status(session, status_event=status_event)

    assert out is message
    create_alert.assert_awaited_once()
    kwargs = create_alert.await_args.kwargs
    assert kwargs["kind"] == operator_alert_service.ALERT_KIND_STATUS_FAILED
    assert kwargs["business_id"] == TEST_BUSINESS_ID
    assert kwargs["message_id"] == MESSAGE_ID


# ---------------------------------------------------------------------------
# Service layer — list + acknowledge
# ---------------------------------------------------------------------------


async def test_acknowledge_alert_sets_fields():
    from app.models.agent import OperatorAlert

    alert = OperatorAlert(
        business_id=TEST_BUSINESS_ID,
        kind=operator_alert_service.ALERT_KIND_SEND_FAILED,
        severity="error",
        title="t",
        body="b",
    )
    alert.id = ALERT_ID
    alert.acknowledged_at = None
    alert.acknowledged_by = None

    session = AsyncMock()
    session.get = AsyncMock(return_value=alert)

    out = await operator_alert_service.acknowledge_alert(
        session, business_id=TEST_BUSINESS_ID, alert_id=ALERT_ID, user_id=TEST_USER_ID
    )
    assert out is alert
    assert alert.acknowledged_at is not None
    assert alert.acknowledged_by == TEST_USER_ID


async def test_acknowledge_alert_cross_business_returns_none():
    from app.models.agent import OperatorAlert

    other = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    alert = OperatorAlert(
        business_id=other,
        kind=operator_alert_service.ALERT_KIND_SEND_FAILED,
        severity="error",
        title="t",
        body="b",
    )
    alert.id = ALERT_ID

    session = AsyncMock()
    session.get = AsyncMock(return_value=alert)

    out = await operator_alert_service.acknowledge_alert(
        session, business_id=TEST_BUSINESS_ID, alert_id=ALERT_ID, user_id=TEST_USER_ID
    )
    assert out is None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_alerts_endpoint(auth_client):
    list_alerts = AsyncMock(return_value=[])
    with patch.object(operator_alert_service, "list_alerts", new=list_alerts):
        resp = await auth_client.get(f"/api/v1/alerts/{TEST_BUSINESS_ID}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    list_alerts.assert_awaited_once()


@pytest.mark.asyncio
async def test_ack_alert_endpoint_404_when_missing(auth_client):
    ack = AsyncMock(return_value=None)
    with patch.object(operator_alert_service, "acknowledge_alert", new=ack):
        resp = await auth_client.post(f"/api/v1/alerts/{TEST_BUSINESS_ID}/{ALERT_ID}/ack")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Migration shape
# ---------------------------------------------------------------------------


def test_migration_creates_table_and_policies():
    path = (
        Path(__file__).resolve().parents[3]
        / "supabase"
        / "migrations"
        / "20260612000002_operator_alerts.sql"
    )
    sql = path.read_text().lower()
    assert "create table operator_alerts" in sql
    assert "enable row level security" in sql
    assert "operator_alerts_select" in sql
    assert "operator_alerts_insert" in sql
    assert "operator_alerts_update" in sql
    assert "ix_operator_alerts_business_unack" in sql
    # Idempotency: every policy guarded by IF NOT EXISTS.
    assert sql.count("if not exists") >= 4
