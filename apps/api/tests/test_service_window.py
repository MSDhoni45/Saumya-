"""Tests for the WhatsApp 24-hour customer service window.

Meta only permits free-form (non-template) outbound messages within 24 hours of
the contact's most recent inbound. Outside that window only approved templates
are allowed. These tests lock in:

- `is_within_service_window` — pure boundary logic
- `get_last_inbound_at` — DB lookup
- `WhatsAppClient.send_template_message` — payload shape
- POST /whatsapp/.../send — 409 OUTSIDE_SERVICE_WINDOW for free-form past window
- POST /whatsapp/.../send — 201 for template sends regardless of window
- agent_tasks._run_turn — AI reply suppressed + system message stored past window
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import BusinessContext, get_current_business
from app.db.session import get_db_session
from app.main import app
from app.services import conversation_service
from app.services.whatsapp_client import WhatsAppClient

from tests.conftest import TEST_BUSINESS_ID, TEST_USER_ID

ACCOUNT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONVERSATION_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MESSAGE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ---------------------------------------------------------------------------
# Pure window logic
# ---------------------------------------------------------------------------


def test_is_within_service_window_just_inside():
    now = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    last_inbound = now - timedelta(hours=23, minutes=59)
    assert conversation_service.is_within_service_window(last_inbound, now=now) is True


def test_is_within_service_window_exactly_24h_is_inside():
    """Boundary: exactly 24h is still inside (≤ window)."""
    now = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    last_inbound = now - timedelta(hours=24)
    assert conversation_service.is_within_service_window(last_inbound, now=now) is True


def test_is_within_service_window_just_outside():
    now = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    last_inbound = now - timedelta(hours=24, seconds=1)
    assert conversation_service.is_within_service_window(last_inbound, now=now) is False


def test_is_within_service_window_none_is_outside():
    """No inbound ever → window has never opened → template only."""
    assert conversation_service.is_within_service_window(None) is False


# ---------------------------------------------------------------------------
# get_last_inbound_at — DB lookup
# ---------------------------------------------------------------------------


async def test_get_last_inbound_at_returns_max():
    expected = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)
    result = MagicMock()
    result.scalar_one_or_none.return_value = expected
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    got = await conversation_service.get_last_inbound_at(session, CONVERSATION_ID)
    assert got == expected


async def test_get_last_inbound_at_none_when_no_inbound():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    got = await conversation_service.get_last_inbound_at(session, CONVERSATION_ID)
    assert got is None


# ---------------------------------------------------------------------------
# WhatsAppClient.send_template_message — payload shape
# ---------------------------------------------------------------------------


async def test_send_template_message_payload_shape():
    client = WhatsAppClient(phone_number_id="PNID", access_token="tok")
    captured: dict = {}

    async def fake_post(path, json):
        captured["path"] = path
        captured["json"] = json
        return {"messages": [{"id": "wamid.tmpl"}]}

    with patch.object(client, "_post", side_effect=fake_post):
        response = await client.send_template_message(
            to="15551234567",
            template_name="hello_world",
            language_code="en_US",
            components=[{"type": "body", "parameters": [{"type": "text", "text": "Rohit"}]}],
        )

    assert response == {"messages": [{"id": "wamid.tmpl"}]}
    assert captured["path"] == "PNID/messages"
    assert captured["json"]["type"] == "template"
    assert captured["json"]["template"]["name"] == "hello_world"
    assert captured["json"]["template"]["language"] == {"code": "en_US"}
    assert captured["json"]["template"]["components"][0]["type"] == "body"


async def test_send_template_message_omits_components_when_none():
    client = WhatsAppClient(phone_number_id="PNID", access_token="tok")
    captured: dict = {}

    async def fake_post(path, json):
        captured["json"] = json
        return {"messages": [{"id": "wamid.tmpl"}]}

    with patch.object(client, "_post", side_effect=fake_post):
        await client.send_template_message(to="15551234567", template_name="hello", language_code="en_US")

    assert "components" not in captured["json"]["template"]


# ---------------------------------------------------------------------------
# Send endpoint — free-form gated, template allowed
# ---------------------------------------------------------------------------


def _connected_account():
    account = MagicMock()
    account.id = ACCOUNT_ID
    account.business_id = TEST_BUSINESS_ID
    account.phone_number_id = "PNID"
    account.access_token = "enc"
    account.status = "connected"
    return account


def _conversation():
    conv = MagicMock()
    conv.id = CONVERSATION_ID
    conv.business_id = TEST_BUSINESS_ID
    return conv


def _stored_message(message_type: str):
    msg = MagicMock()
    msg.id = MESSAGE_ID
    msg.conversation_id = CONVERSATION_ID
    msg.direction = "outbound"
    msg.sender_type = "agent"
    msg.message_type = message_type
    msg.content = "hi"
    msg.media_url = None
    msg.status = "sent"
    msg.delivered_at = None
    msg.read_at = None
    msg.failed_at = None
    msg.error_code = None
    msg.error_title = None
    msg.created_at = datetime.now(tz=timezone.utc)
    return msg


@pytest_asyncio.fixture
async def send_client():
    """Auth client wired with a permissive mock DB. Each test patches the
    service-layer helpers explicitly — avoids reaching into mock internals to
    fake DB rows."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.get = AsyncMock(return_value=_connected_account())
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_current_business] = lambda: BusinessContext(
        user_id=TEST_USER_ID, business_id=TEST_BUSINESS_ID, role="business_admin"
    )

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db

    app.dependency_overrides.clear()


async def test_send_text_outside_window_returns_409(send_client):
    client, _ = send_client
    url = f"/api/v1/whatsapp/{TEST_BUSINESS_ID}/accounts/{ACCOUNT_ID}/send"

    with (
        patch("app.api.v1.whatsapp.conversation_service.get_or_create_conversation", new=AsyncMock(return_value=_conversation())),
        patch(
            "app.api.v1.whatsapp.conversation_service.get_last_inbound_at",
            new=AsyncMock(return_value=datetime.now(tz=timezone.utc) - timedelta(hours=25)),
        ),
        patch("app.api.v1.whatsapp.decrypt_secret", return_value="tok"),
    ):
        resp = await client.post(url, json={"to": "15551234567", "message_type": "text", "text": "hi"})

    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "OUTSIDE_SERVICE_WINDOW"
    assert body["detail"]["requires_template"] is True


async def test_send_text_inside_window_succeeds(send_client):
    client, _ = send_client
    url = f"/api/v1/whatsapp/{TEST_BUSINESS_ID}/accounts/{ACCOUNT_ID}/send"

    with (
        patch("app.api.v1.whatsapp.conversation_service.get_or_create_conversation", new=AsyncMock(return_value=_conversation())),
        patch(
            "app.api.v1.whatsapp.conversation_service.get_last_inbound_at",
            new=AsyncMock(return_value=datetime.now(tz=timezone.utc) - timedelta(minutes=10)),
        ),
        patch(
            "app.api.v1.whatsapp.conversation_service.store_outbound_message",
            new=AsyncMock(return_value=_stored_message("text")),
        ),
        patch("app.api.v1.whatsapp.decrypt_secret", return_value="tok"),
        patch.object(WhatsAppClient, "send_text_message", new=AsyncMock(return_value={"messages": [{"id": "wamid.x"}]})),
        patch("app.api.v1.whatsapp.publish_new_message", new=AsyncMock()),
    ):
        resp = await client.post(url, json={"to": "15551234567", "message_type": "text", "text": "hi"})

    assert resp.status_code == 201
    assert resp.json()["whatsapp_message_id"] == "wamid.x"


async def test_send_template_outside_window_succeeds(send_client):
    """Templates bypass the window gate — they're the only way to re-engage."""
    client, _ = send_client
    url = f"/api/v1/whatsapp/{TEST_BUSINESS_ID}/accounts/{ACCOUNT_ID}/send"

    send_template = AsyncMock(return_value={"messages": [{"id": "wamid.tmpl"}]})

    with (
        patch("app.api.v1.whatsapp.conversation_service.get_or_create_conversation", new=AsyncMock(return_value=_conversation())),
        # get_last_inbound_at must NOT be consulted on the template path — if it
        # is called, surface an explicit failure.
        patch(
            "app.api.v1.whatsapp.conversation_service.get_last_inbound_at",
            new=AsyncMock(side_effect=AssertionError("window must not be checked for template sends")),
        ),
        patch(
            "app.api.v1.whatsapp.conversation_service.store_outbound_message",
            new=AsyncMock(return_value=_stored_message("template")),
        ),
        patch("app.api.v1.whatsapp.decrypt_secret", return_value="tok"),
        patch.object(WhatsAppClient, "send_template_message", new=send_template),
        patch("app.api.v1.whatsapp.publish_new_message", new=AsyncMock()),
    ):
        resp = await client.post(
            url,
            json={
                "to": "15551234567",
                "message_type": "template",
                "template_name": "hello_world",
                "language_code": "en_US",
            },
        )

    assert resp.status_code == 201
    send_template.assert_awaited_once()
    args, kwargs = send_template.call_args
    # Method called with positional (to, name, lang, components) — flexible check.
    assert "hello_world" in (list(args) + list(kwargs.values()))


async def test_send_template_missing_required_fields_returns_422(send_client):
    client, _ = send_client
    url = f"/api/v1/whatsapp/{TEST_BUSINESS_ID}/accounts/{ACCOUNT_ID}/send"

    resp = await client.post(
        url,
        json={"to": "15551234567", "message_type": "template"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Worker AI reply — outside window suppresses send + writes system message
# ---------------------------------------------------------------------------


async def test_ai_reply_outside_window_suppresses_and_logs_system_message():
    from app.workers.tasks import agent_tasks

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

    agent = MagicMock()
    store_system = AsyncMock()
    send_text = AsyncMock()

    with (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=agent)),
        patch.object(
            agent_tasks.conversation_service,
            "get_last_inbound_at",
            new=AsyncMock(return_value=datetime.now(tz=timezone.utc) - timedelta(hours=25)),
        ),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=store_system),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=AsyncMock()) as gen,
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    # AI generation never invoked, no WhatsApp send, but a system message landed.
    gen.assert_not_called()
    send_text.assert_not_called()
    store_system.assert_awaited_once()


async def test_ai_reply_inside_window_proceeds_to_send():
    from app.workers.tasks import agent_tasks

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

    agent_reply = MagicMock()
    agent_reply.reply = "Hello back!"

    send_text = AsyncMock(return_value={"messages": [{"id": "wamid.ai"}]})

    with (
        patch.object(agent_tasks, "check_usage_limit", new=AsyncMock()),
        patch.object(agent_tasks, "increment_usage", new=AsyncMock()),
        patch.object(agent_tasks.sales_agent_service, "get_active_agent", new=AsyncMock(return_value=MagicMock())),
        patch.object(
            agent_tasks.conversation_service,
            "get_last_inbound_at",
            new=AsyncMock(return_value=datetime.now(tz=timezone.utc) - timedelta(minutes=5)),
        ),
        patch.object(agent_tasks, "_recent_messages", new=AsyncMock(return_value=[])),
        patch.object(agent_tasks.sales_agent_service, "generate_agent_reply", new=AsyncMock(return_value=agent_reply)),
        patch.object(WhatsAppClient, "send_text_message", new=send_text),
        patch.object(agent_tasks.conversation_service, "store_outbound_message", new=AsyncMock(return_value=_stored_message("text"))),
        patch.object(
            agent_tasks.sales_agent_service,
            "reserve_interaction",
            new=AsyncMock(return_value=uuid.uuid4()),
        ),
        patch.object(agent_tasks.sales_agent_service, "finalize_interaction", new=AsyncMock()),
        patch.object(agent_tasks.conversation_service, "store_system_message", new=AsyncMock()) as store_system,
        patch.object(agent_tasks, "decrypt_secret", return_value="tok"),
    ):
        await agent_tasks._run_turn(session, CONVERSATION_ID, MESSAGE_ID)

    send_text.assert_awaited_once()
    store_system.assert_not_called()
