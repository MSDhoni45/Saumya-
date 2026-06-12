"""Tests for WhatsApp Cloud API status callback handling.

These lock in the lifecycle that the prior implementation silently dropped: the
webhook dispatcher used to short-circuit when `value.messages` was empty, which
meant every `statuses[]`-only delivery (sent / delivered / read / failed) was
discarded before any handler ran. The new behaviour must:

- accept status-only payloads
- advance `Message.status` monotonically (sent < delivered < read; failed terminal)
- treat duplicate redeliveries as no-ops (Meta retries on any non-2xx)
- ignore unknown `whatsapp_message_id` values (other env's traffic, races)
- publish SSE realtime events for every forward transition
- write the matching timestamp + error metadata columns
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.whatsapp import WebhookStatus, WebhookStatusError
from app.services import conversation_service


# ---------------------------------------------------------------------------
# apply_message_status — pure state machine, no I/O beyond the session
# ---------------------------------------------------------------------------


def _make_message(*, status: str = "sent") -> MagicMock:
    message = MagicMock()
    message.id = uuid.uuid4()
    message.conversation_id = uuid.uuid4()
    message.whatsapp_message_id = "wamid.test"
    message.status = status
    message.delivered_at = None
    message.read_at = None
    message.failed_at = None
    message.error_code = None
    message.error_title = None
    return message


def _session_returning(message):
    result = MagicMock()
    result.scalar_one_or_none.return_value = message
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


async def test_apply_status_sent_to_delivered_advances_and_writes_timestamp():
    message = _make_message(status="sent")
    session = _session_returning(message)

    event = WebhookStatus(
        id="wamid.test",
        status="delivered",
        timestamp="1717000000",
        recipient_id="15551234567",
    )
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is message
    assert message.status == "delivered"
    assert message.delivered_at == datetime.fromtimestamp(1717000000, tz=timezone.utc)
    assert message.read_at is None
    assert message.failed_at is None


async def test_apply_status_delivered_to_read_advances():
    message = _make_message(status="delivered")
    session = _session_returning(message)

    event = WebhookStatus(id="wamid.test", status="read", timestamp="1717000060")
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is message
    assert message.status == "read"
    assert message.read_at == datetime.fromtimestamp(1717000060, tz=timezone.utc)


async def test_apply_status_failed_records_error_metadata():
    message = _make_message(status="sent")
    session = _session_returning(message)

    event = WebhookStatus(
        id="wamid.test",
        status="failed",
        timestamp="1717000999",
        errors=[WebhookStatusError(code=131047, title="Re-engagement message")],
    )
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is message
    assert message.status == "failed"
    assert message.failed_at == datetime.fromtimestamp(1717000999, tz=timezone.utc)
    assert message.error_code == "131047"
    assert message.error_title == "Re-engagement message"


async def test_apply_status_duplicate_is_noop():
    """Meta routinely redelivers the same callback — re-application must not bump anything."""
    message = _make_message(status="delivered")
    original_delivered_at = datetime.fromtimestamp(1717000000, tz=timezone.utc)
    message.delivered_at = original_delivered_at
    session = _session_returning(message)

    event = WebhookStatus(id="wamid.test", status="delivered", timestamp="1717000500")
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is None
    assert message.status == "delivered"
    assert message.delivered_at == original_delivered_at, "duplicate must not overwrite timestamp"


async def test_apply_status_out_of_order_does_not_regress():
    """`delivered` arriving after `read` (Meta reorders under load) must not move state backwards."""
    message = _make_message(status="read")
    message.read_at = datetime.fromtimestamp(1717000060, tz=timezone.utc)
    session = _session_returning(message)

    event = WebhookStatus(id="wamid.test", status="delivered", timestamp="1717000000")
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is None
    assert message.status == "read"


async def test_apply_status_failed_is_terminal():
    """Once a send is marked failed, no later delivered/read may resurrect it."""
    message = _make_message(status="failed")
    message.failed_at = datetime.fromtimestamp(1717000999, tz=timezone.utc)
    session = _session_returning(message)

    event = WebhookStatus(id="wamid.test", status="read", timestamp="1717001000")
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is None
    assert message.status == "failed"


async def test_apply_status_unknown_message_id_is_noop():
    """A callback for a wamid we never stored must log and no-op, never raise."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    event = WebhookStatus(id="wamid.unknown", status="delivered", timestamp="1717000000")
    updated = await conversation_service.apply_message_status(session, status_event=event)

    assert updated is None


# ---------------------------------------------------------------------------
# Realtime publish
# ---------------------------------------------------------------------------


async def test_publish_message_status_sends_to_conversation_channel():
    from app.services import realtime

    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()

    with patch.object(realtime, "_get_redis", return_value=fake_redis):
        await realtime.publish_message_status("conv-1", "msg-9", "delivered")

    fake_redis.publish.assert_awaited_once()
    channel, payload = fake_redis.publish.await_args.args
    assert channel == "conv:conv-1:msg"
    assert "delivered" in payload
    assert "msg-9" in payload
    assert "message_status" in payload


async def test_publish_message_status_swallows_redis_error():
    """A Redis outage must never propagate — the webhook 200 has already been promised."""
    from app.services import realtime

    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock(side_effect=RuntimeError("redis down"))

    with patch.object(realtime, "_get_redis", return_value=fake_redis):
        # Must not raise.
        await realtime.publish_message_status("conv-1", "msg-9", "failed")
