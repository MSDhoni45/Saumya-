"""
Server-Sent Events (SSE) real-time layer backed by Redis pub/sub.

Why SSE rather than WebSockets: SSE is one-directional (server → client) which
is all the inbox needs for new-message notifications — the browser already has
the `send` API via REST. SSE works over plain HTTP, so it passes through the
Next.js rewrite proxy without a WS-upgrade dance, and reconnects automatically
on disconnect.

Channel naming
--------------
  conv:{conversation_id}:msg     — new / updated messages for a single thread
  biz:{business_id}:alerts       — operator-visible pipeline alerts
"""

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

_KEEPALIVE_SECONDS = 25.0
_POLL_TIMEOUT = 1.0

# Shared connection pool — reused across all publish calls and SSE streams.
# redis-py's `from_url` creates a connection pool internally; calling it once
# and holding the reference avoids creating/destroying a connection per request.
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True, max_connections=50)
    return _redis


async def publish_message_status(conversation_id: str, message_id: str, status: str) -> None:
    """Publish a status transition (sent/delivered/read/failed) for an existing message.

    Goes on the same `conv:{id}:msg` channel as new messages — the SSE consumer
    distinguishes by payload shape (status events carry a `status` field plus a
    message_id, no `direction`). Errors swallowed for the same reason as
    `publish_new_message`.
    """
    payload = {"event": "message_status", "message_id": message_id, "status": status}
    try:
        await _get_redis().publish(f"conv:{conversation_id}:msg", json.dumps(payload))
    except Exception:  # noqa: BLE001
        pass


async def publish_new_message(conversation_id: str, message_data: dict) -> None:
    """Publish a serialised MessageResponse to the conversation's channel.

    Swallows all errors — a Redis outage must never break the HTTP response
    that triggered the publish (webhook 200, agent send 201, etc.).
    """
    try:
        await _get_redis().publish(f"conv:{conversation_id}:msg", json.dumps(message_data))
    except Exception:  # noqa: BLE001
        pass


async def publish_operator_alert(
    *, business_id: str, alert_id: str, kind: str, severity: str, title: str
) -> None:
    """Broadcast a new operator alert to a business's SSE channel.

    Same swallow-errors policy as `publish_new_message` — a Redis outage must
    never break the failure-recording path that triggered the alert.
    """
    payload = {
        "event": "operator_alert",
        "alert_id": alert_id,
        "kind": kind,
        "severity": severity,
        "title": title,
    }
    try:
        await _get_redis().publish(f"biz:{business_id}:alerts", json.dumps(payload))
    except Exception:  # noqa: BLE001
        pass


async def stream_conversation(conversation_id: str) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted text for a conversation thread.

    Each `data:` line carries a JSON-encoded MessageResponse object (the same
    shape as the REST endpoint). Comment lines (`:`...) are keepalive pings that
    prevent proxy/CDN timeouts; the browser's EventSource ignores them.
    """
    pubsub = _get_redis().pubsub()
    channel = f"conv:{conversation_id}:msg"
    await pubsub.subscribe(channel)

    yield "event: connected\ndata: {}\n\n"

    last_keepalive = time.monotonic()
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_POLL_TIMEOUT)
            if msg and msg["type"] == "message":
                yield f"data: {msg['data']}\n\n"

            if time.monotonic() - last_keepalive >= _KEEPALIVE_SECONDS:
                yield ": keepalive\n\n"
                last_keepalive = time.monotonic()
    except (GeneratorExit, asyncio.CancelledError):
        pass
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
